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
      conntrack -E -e destroy -o extended,timestamp 2>/dev/null | while IFS= read -r line; do
        # Example line (fields vary in count by protocol; parse what's
        # common to all: protocol name, src/dst ip:port, packet/byte
        # counters appear twice -- original and reply direction).
        proto=$(awk '{print $4}' <<<"$line")
        src=$(grep -oP 'src=\K[^ ]+' <<<"$line" | head -1)
        dst=$(grep -oP 'dst=\K[^ ]+' <<<"$line" | head -1)
        sport=$(grep -oP 'sport=\K[^ ]+' <<<"$line" | head -1)
        dport=$(grep -oP 'dport=\K[^ ]+' <<<"$line" | head -1)
        packets=$(grep -oP 'packets=\K[^ ]+' <<<"$line" | awk '{s+=$1} END{print s+0}')
        bytes=$(grep -oP 'bytes=\K[^ ]+' <<<"$line" | awk '{s+=$1} END{print s+0}')

        [ -n "$src" ] && [ -n "$dst" ] || continue

        jq -nc \
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
          }' | "$capture_bin" write --capture-root "$capture_root" --lane netflow
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
