# capture-netflow: L0 network flow metadata via kernel conntrack events.
#
# The L0 slice of zeek-class flow metadata: 5-tuple + byte/packet counters +
# duration per connection, sourced from `conntrack -E` (netlink conntrack
# events), which the kernel already tracks for NAT/firewall state -- no
# packet capture, no TLS interception, no payload of any kind. DNS query
# content and TLS SNI need a real packet-inspection layer (tshark/scapy over
# DNS responses and the TLS ClientHello), a different mechanism entirely and
# out of scope here.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix.paths) capturesRoot;
  laneDir = "${capturesRoot}/netflow";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  streamer = pkgs.writeShellApplication {
    name = "capture-netflow-stream";
    runtimeInputs = [
      pkgs.conntrack-tools
      pkgs.gawk
      pkgs.jq
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      capture_bin="$1"
      capture_root="$2"

      # `conntrack -E -e destroy` emits one line per connection teardown
      # with its final byte/packet counters -- exactly the "flow record"
      # shape (start implied by first-seen timestamp, end = this event),
      # not a live stream of every packet. `-o extended` gives numeric
      # ports/protocols instead of service-name lookups (no /etc/services
      # dependency, stable field positions).
      # Field extraction must be ONE awk pass, never a per-field grep chain:
      # a record for a portless protocol (ICMP) makes grep exit 1, pipefail
      # promotes that to the pipeline status and set -e kills the read loop,
      # while conntrack keeps running (systemd sets IgnoreSIGPIPE=true) --
      # the unit then sits "active (running)" writing nothing, forever. awk
      # exits 0 whether or not a key is present. Keys appear twice (original
      # and reply direction): take the first src/dst/port, SUM packets/bytes.
      conntrack -E -e destroy -o extended,timestamp 2>/dev/null \
        | awk '{
            # proto by pattern, not column index: column positions shift with
            # the -o flags ($4 under `-o timestamp` is the address family).
            proto = ""; src = ""; dst = ""; sport = ""; dport = ""; pk = 0; by = 0
            for (i = 1; i <= NF; i++)
              if ($i ~ /^(tcp|udp|udplite|icmp|icmpv6|sctp|dccp|gre|unknown)$/) { proto = $i; break }
            for (i = 1; i <= NF; i++) {
              eq = index($i, "=")
              if (eq == 0) continue
              k = substr($i, 1, eq - 1); v = substr($i, eq + 1)
              if (k == "src") { if (src == "") src = v }
              else if (k == "dst") { if (dst == "") dst = v }
              else if (k == "sport") { if (sport == "") sport = v }
              else if (k == "dport") { if (dport == "") dport = v }
              else if (k == "packets") pk += v
              else if (k == "bytes") by += v
            }
            if (src != "" && dst != "")
              printf "%s\t%s\t%s\t%s\t%s\t%d\t%d\n", proto, src, dst, sport, dport, pk, by
          }' \
        | while IFS="$(printf '\t')" read -r proto src dst sport dport packets bytes; do
        # A malformed record must not take the stream down with it. Report it
        # to the journal and carry on, rather than `|| true`, which would make
        # the loss invisible.
        if ! jq -nc \
          --arg proto "$proto" \
          --arg src "$src" \
          --arg dst "$dst" \
          --arg sport "$sport" \
          --arg dport "$dport" \
          --arg packets "$packets" \
          --arg bytes "$bytes" \
          '{
            proto: $proto,
            src: $src,
            dst: $dst,
            sport: ($sport | tonumber? // null),
            dport: ($dport | tonumber? // null),
            packets: ($packets | tonumber? // 0),
            bytes: ($bytes | tonumber? // 0)
          }' | "$capture_bin" write --capture-root "$capture_root" --lane netflow; then
          echo "capture-netflow: dropped a record ($proto $src -> $dst)" >&2
        fi
      done
    '';
  };
in
mkServiceModule {
  name = "capture-netflow";
  description = "L0 network flow metadata (5-tuple + byte/packet counters) via kernel conntrack events -- no packet capture, no TLS interception";
  surface = {
    unit = "sinnix-capture-netflow.service";
    manager = "system";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "netflow";
        path = laneDir;
        cadenceSeconds = null;
        # Event-driven, not polled -- staleness here means "no connection
        # torn down in an hour", which is a real signal on a workstation
        # that's normally always making/closing connections, but sleep or
        # a quiet stretch can legitimately produce a gap.
        staleAfterSeconds = 3600;
      }
    ];
  };
  configFn =
    { config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0755 ${username} users -"
      ];

      # Both default to off. Without nf_conntrack_acct every flow records
      # packets=0 bytes=0 -- the counters that are the lane's whole point.
      # Without nf_conntrack_timestamp there is no flow-START time: `-o
      # timestamp` alone stamps the DESTROY event, so duration is underivable.
      boot.kernel.sysctl = {
        "net.netfilter.nf_conntrack_acct" = 1;
        "net.netfilter.nf_conntrack_timestamp" = 1;
      };

      systemd.services.sinnix-capture-netflow = {
        description = "Stream kernel conntrack flow-teardown events into the capture lake";
        wantedBy = [ "multi-user.target" ];
        after = [ "network.target" ];
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-capture-netflow.service";
          overrides = {
            Type = "simple";
            User = username;
            Group = "users";
            ExecStart = lib.concatStringsSep " " [
              "${streamer}/bin/capture-netflow-stream"
              "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
              capturesRoot
            ];
            Restart = "on-failure";
            RestartSec = "10s";
            # conntrack -E needs CAP_NET_ADMIN to open the netlink conntrack
            # socket; granted as an ambient capability to the operator user
            # rather than running the whole unit as root.
            AmbientCapabilities = [ "CAP_NET_ADMIN" ];
            NoNewPrivileges = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [ laneDir ];
            Environment = [ "TMPDIR=/tmp" ];
            PrivateTmp = true;
          };
        };
      };
    };
} args
