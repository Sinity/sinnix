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
  lakeRoot = config.sinnix.paths.machineRoot;
  laneDir = "${lakeRoot}/netflow";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  # A lane that cannot record its counters must fail, not run quietly and
  # write zeroes: "missing data is missing, never zero". Runs as root
  # (PermissionsStartOnly-style via `+`) because the sysctls are root-only.
  requireAccounting = pkgs.writeShellApplication {
    name = "capture-netflow-require-accounting";
    runtimeInputs = [ pkgs.coreutils ];
    text = ''
      status=0
      for knob in nf_conntrack_acct nf_conntrack_timestamp; do
        path="/proc/sys/net/netfilter/$knob"
        if [ ! -e "$path" ]; then
          echo "capture-netflow: $path is absent (nf_conntrack not loaded)" >&2
          status=1
          continue
        fi
        # Re-apply rather than only assert: a module loaded after boot resets
        # these to their compiled-in default of 0.
        echo 1 >"$path" || true
        value="$(cat "$path")"
        if [ "$value" != "1" ]; then
          echo "capture-netflow: $knob is $value, so every flow would record packets=0 bytes=0" >&2
          status=1
        fi
      done
      exit "$status"
    '';
  };

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
        | jq -Rc --unbuffered 'split("\t")
            | {
                proto: .[0],
                src: .[1],
                dst: .[2],
                sport: (.[3] | tonumber? // null),
                dport: (.[4] | tonumber? // null),
                packets: (.[5] | tonumber? // 0),
                bytes: (.[6] | tonumber? // 0)
              }' \
        | "$capture_bin" write --capture-root "$capture_root" --lane netflow --stream
      # One jq and one writer for the whole stream, not one of each per flow.
      # The previous per-record shape spawned two processes for every
      # connection teardown on the host -- on a busy desktop that is hundreds
      # of thousands of process starts a day. `--stream` keeps the writer's
      # own "report the bad record and keep draining" contract.
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
      #
      # These knobs only EXIST once nf_conntrack is loaded. Declaring them
      # alone is not enough and silently was not: systemd-sysctl runs at boot
      # whether or not the module is present and merely logs "Couldn't write
      # '1' to 'net/netfilter/nf_conntrack_acct', ignoring: No such file or
      # directory" before moving on, so the lane spent its whole life
      # recording bytes=0 packets=0 while looking healthy. Loading the module
      # explicitly puts it in place before systemd-sysctl (which is ordered
      # After=systemd-modules-load.service), and the unit's own ExecStartPre
      # below refuses to start a lane that cannot record its counters.
      boot.kernelModules = [ "nf_conntrack" ];
      boot.kernel.sysctl = {
        "net.netfilter.nf_conntrack_acct" = 1;
        "net.netfilter.nf_conntrack_timestamp" = 1;
      };

      systemd.services.sinnix-capture-netflow = {
        description = "Stream kernel conntrack flow-teardown events into the capture lake";
        wantedBy = [ "multi-user.target" ];
        after = [ "network.target" ];
        # A lane whose accounting precondition cannot be met is permanently
        # broken, not transiently: park it after a few tries instead of
        # churning the journal forever.
        startLimitIntervalSec = 300;
        startLimitBurst = 5;
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-capture-netflow.service";
          overrides = {
            Type = "simple";
            User = username;
            Group = "users";
            # `+` runs this one step as root: the unit itself stays unprivileged.
            ExecStartPre = "+${requireAccounting}/bin/capture-netflow-require-accounting";
            ExecStart = lib.concatStringsSep " " [
              "${streamer}/bin/capture-netflow-stream"
              "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
              lakeRoot
            ];
            Restart = "on-failure";
            RestartSec = "10s";
            # systemd defaults this to true, which is what let the lane sit
            # "active (running)" while writing nothing: when the reader end of
            # the pipeline died, conntrack kept running and kept failing every
            # write() with EPIPE instead of dying on SIGPIPE. Let the signal
            # through so a broken pipeline is a unit failure that restarts,
            # not a silent one that looks healthy.
            IgnoreSIGPIPE = false;
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
