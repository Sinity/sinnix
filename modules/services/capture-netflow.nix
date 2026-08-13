# capture-netflow: L0 network flow metadata via kernel conntrack events.
#
# sinnix-0cqk asked for zeek-class flow metadata -- deliberately deferred
# from the main capture program, not dead. This is the L0 slice of that:
# 5-tuple + byte/packet counters + duration per connection, sourced from
# `conntrack -E` (netlink conntrack events), which the kernel already
# tracks for NAT/firewall state -- no packet capture, no TLS interception,
# no payload of any kind. DNS query content and TLS SNI extraction need an
# actual packet-inspection layer (tshark/scapy parsing DNS responses and
# TLS ClientHello) -- a materially different mechanism from conntrack
# events, and out of scope for this pass; DNS query logging specifically
# also brushes against the standing caution recorded for the router's own
# dnsmasq query log ("must never be permanently enabled -- both a CPU cost
# and the most sensitive stream on the network"), so it needs its own
# deliberate pass, not a drive-by addition here.
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
      # Field extraction is ONE awk pass, not a per-field grep chain, because
      # of how the previous shape failed. Each field was pulled with
      # `grep -oP ... | head -1` inside a command substitution; a conntrack
      # record for a protocol with no ports (ICMP) makes that grep exit 1,
      # `pipefail` promotes it to the pipeline's status, and `set -e` then
      # killed the read loop on the first such packet. conntrack itself
      # survived -- systemd sets IgnoreSIGPIPE=true for services, so instead
      # of dying on the broken pipe it kept write()ing into a pipe with no
      # reader forever. The unit stayed "active (running)" with zero bytes
      # written and never restarted, because nothing ever crashed.
      #
      # awk exits 0 whether or not a key is present, so no protocol shape can
      # tear the loop down. Keys appear twice (original and reply direction):
      # take the first src/dst/port, and SUM packets/bytes across both.
      conntrack -E -e destroy -o extended,timestamp 2>/dev/null \
        | awk '{
            # proto by pattern, not column index. The old code read $4, which
            # with `-o timestamp` is the address-family NUMBER (2), not the
            # L4 name -- every record was labelled "2". Column positions shift
            # with the -o flags, so match the name instead.
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
        # A malformed record must not take the stream down with it (that is
        # the bug above in miniature). Report it to the journal and carry on,
        # rather than `|| true`, which would make the loss invisible.
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

      # Without these the lane records every flow with packets=0 bytes=0 --
      # the counters that are its whole point. conntrack only reports
      # per-flow accounting when nf_conntrack_acct is on, and it is off by
      # default (measured on this host: both read 0). Flow-start timestamps
      # come from nf_conntrack_timestamp; `-o timestamp` alone stamps when
      # the DESTROY event was observed, which is the flow's END, so without
      # this there is nothing to derive a duration from.
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
