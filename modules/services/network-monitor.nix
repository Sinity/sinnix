# network-monitor: Continuous WAN link quality logger + sinnix-gw log sync
#
# Two components:
#   1. Local probe (every 5 min): comprehensive JSONL log of link quality
#   2. Router sync (every 30 min): pulls wan-monitor.jsonl from sinnix-gw,
#      appends to local archive, truncates on router to free NAND.
#
# Data: ${capturesRoot}/network/{sinnix-prime,sinnix-gw}.jsonl
# No rotation on sinnix-prime (/realm/data has plenty of space).
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  ...
}@args:
let
  inherit (config.sinnix.paths) capturesRoot;
  dataDir = "${capturesRoot}/network";
  gateway = "192.168.1.1";
  routerAddr = gateway;

  probe = pkgs.writeShellApplication {
    name = "network-probe";
    runtimeInputs = with pkgs; [
      bind
      iputils
      iproute2
      ethtool
      curl
      jq
      coreutils
      gawk
      gnugrep
    ];
    text = ''
      set -euo pipefail
      DIR="${dataDir}"
      mkdir -p "$DIR"
      TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

      # ── Ping targets (5 pings each, 2s timeout) ──
      ping_json() {
        local ip="$1"
        local out
        out=$(ping -c 5 -W 2 -q "$ip" 2>/dev/null) || true
        local loss avg min max
        loss=$(echo "$out" | grep -oP '[0-9.]+(?=% packet loss)' || echo "100")
        avg=$(echo "$out" | grep rtt | awk -F'[/ ]' '{print $8}' || echo "null")
        min=$(echo "$out" | grep rtt | awk -F'[/ ]' '{print $7}' || echo "null")
        max=$(echo "$out" | grep rtt | awk -F'[/ ]' '{print $9}' || echo "null")
        printf '{"ip":"%s","loss":%s,"min_ms":%s,"avg_ms":%s,"max_ms":%s}' \
          "$ip" "''${loss:-100}" "''${min:-null}" "''${avg:-null}" "''${max:-null}"
      }

      P_GW=$(ping_json "${gateway}")
      P_CF=$(ping_json "1.1.1.1")
      P_GG=$(ping_json "8.8.8.8")
      P_CDN=$(ping_json "104.16.0.1")

      # ── Bufferbloat: ping during mini-download ──
      BLOAT="null"
      if curl -4 -o /dev/null -s --max-time 6 "https://speed.cloudflare.com/__down?bytes=10000000" & CURL_PID=$!; then
        sleep 1
        BLOAT_OUT=$(ping -c 4 -W 2 -q 8.8.8.8 2>/dev/null) || true
        BLOAT_AVG=$(echo "$BLOAT_OUT" | grep rtt | awk -F'[/ ]' '{print $8}' || echo "null")
        BLOAT_LOSS=$(echo "$BLOAT_OUT" | grep -oP '[0-9.]+(?=% packet loss)' || echo "100")
        BLOAT="{\"avg_ms\":''${BLOAT_AVG:-null},\"loss\":''${BLOAT_LOSS:-100}}"
        kill $CURL_PID 2>/dev/null || true
        wait $CURL_PID 2>/dev/null || true
      fi

      # ── Interface stats ──
      DEV="enp6s0"
      RX_BYTES=$(cat /sys/class/net/$DEV/statistics/rx_bytes)
      TX_BYTES=$(cat /sys/class/net/$DEV/statistics/tx_bytes)
      RX_ERRORS=$(cat /sys/class/net/$DEV/statistics/rx_errors)
      TX_ERRORS=$(cat /sys/class/net/$DEV/statistics/tx_errors)
      RX_DROPPED=$(cat /sys/class/net/$DEV/statistics/rx_dropped)
      TX_DROPPED=$(cat /sys/class/net/$DEV/statistics/tx_dropped)
      COLLISIONS=$(cat /sys/class/net/$DEV/statistics/collisions)

      # ── NIC link status ──
      SPEED=$(ethtool $DEV 2>/dev/null | grep -oP 'Speed: \K[0-9]+' || echo "0")
      DUPLEX=$(ethtool $DEV 2>/dev/null | grep -oP 'Duplex: \K\w+' || echo "unknown")
      LINK=$(ethtool $DEV 2>/dev/null | grep -oP 'Link detected: \K\w+' || echo "no")

      # ── TCP stack stats ──
      TCP_LINE=$(grep '^Tcp:' /proc/net/snmp | tail -1)
      TCP_RETRANS=$(echo "$TCP_LINE" | awk '{print $13}')
      TCP_INERRS=$(echo "$TCP_LINE" | awk '{print $14}')
      TCP_OUTRSTS=$(echo "$TCP_LINE" | awk '{print $15}')

      # ── Connection counts ──
      ESTAB=$(ss -tn state established | tail -n+2 | wc -l)
      TIMEWAIT=$(ss -tn state time-wait | tail -n +2 | wc -l)

      # ── DNS resolution latency ──
      DNS_START=$(date +%s%N)
      nslookup example.com >/dev/null 2>&1 || true
      DNS_END=$(date +%s%N)
      DNS_MS=$(( (DNS_END - DNS_START) / 1000000 ))

      # ── PMTU check ──
      PMTU_OK="false"
      if ping -c 1 -W 2 -M "do" -s 1464 8.8.8.8 >/dev/null 2>&1; then
        PMTU_OK="true"
      fi

      # ── Conntrack ──
      CT_COUNT=$(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null || echo 0)
      CT_MAX=$(cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo 0)

      # ── Write JSONL ──
      jq -nc \
        --arg ts "$TS" \
        --argjson gw "$P_GW" \
        --argjson cf "$P_CF" \
        --argjson gg "$P_GG" \
        --argjson cdn "$P_CDN" \
        --argjson bloat "$BLOAT" \
        --argjson rx_bytes "$RX_BYTES" --argjson tx_bytes "$TX_BYTES" \
        --argjson rx_err "$RX_ERRORS" --argjson tx_err "$TX_ERRORS" \
        --argjson rx_drop "$RX_DROPPED" --argjson tx_drop "$TX_DROPPED" \
        --argjson collisions "$COLLISIONS" \
        --arg speed "$SPEED" --arg duplex "$DUPLEX" --arg link "$LINK" \
        --argjson tcp_retrans "$TCP_RETRANS" --argjson tcp_inerrs "$TCP_INERRS" \
        --argjson tcp_outrsts "$TCP_OUTRSTS" \
        --argjson estab "$ESTAB" --argjson timewait "$TIMEWAIT" \
        --argjson dns_ms "$DNS_MS" \
        --argjson pmtu_1492 "$PMTU_OK" \
        --argjson ct_count "$CT_COUNT" --argjson ct_max "$CT_MAX" \
        '{
          ts: $ts,
          ping: {gateway: $gw, cloudflare: $cf, google: $gg, cdn: $cdn},
          bloat: $bloat,
          iface: {rx_bytes: $rx_bytes, tx_bytes: $tx_bytes, rx_err: $rx_err, tx_err: $tx_err, rx_drop: $rx_drop, tx_drop: $tx_drop, collisions: $collisions},
          nic: {speed_mbps: ($speed | tonumber), duplex: $duplex, link: $link},
          tcp: {retrans: $tcp_retrans, in_errs: $tcp_inerrs, out_rsts: $tcp_outrsts, established: $estab, timewait: $timewait},
          dns_ms: $dns_ms,
          pmtu_1492: $pmtu_1492,
          conntrack: {count: $ct_count, max: $ct_max}
        }' >> "$DIR/sinnix-prime.jsonl"
    '';
  };

  syncScript = pkgs.writeShellApplication {
    name = "network-monitor-sync";
    runtimeInputs = with pkgs; [
      openssh
      coreutils
    ];
    text = ''
      set -euo pipefail
      DIR="${dataDir}"
      mkdir -p "$DIR"
      REMOTE="root@${routerAddr}"
      SSH_COMMON=(-o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
      # Append router logs then truncate on router to free NAND
      if scp -O "''${SSH_COMMON[@]}" "$REMOTE:/overlay/log/wan-monitor.jsonl" "$DIR/.sinnix-gw-incoming.jsonl" 2>/dev/null; then
        cat "$DIR/.sinnix-gw-incoming.jsonl" >> "$DIR/sinnix-gw.jsonl"
        rm "$DIR/.sinnix-gw-incoming.jsonl"
        ssh "''${SSH_COMMON[@]}" "$REMOTE" '> /overlay/log/wan-monitor.jsonl' 2>/dev/null || true
      else
        echo "sync failed (router unreachable?)"
      fi
    '';
  };
in
mkServiceModule {
  name = "network-monitor";
  description = "WAN link quality monitor + sinnix-gw log sync";
  health = {
    unit = "network-probe.timer";
    type = "timer";
    restartable = true;
  };
  configFn =
    { cfg, lib, ... }:
    {
      environment.systemPackages = [
        probe
        syncScript
      ];

      systemd.tmpfiles.rules = [
        "d ${dataDir} 0755 root root -"
      ];

      systemd.services.network-probe = {
        description = "Network link quality probe";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = lib.getExe probe;
          TimeoutStartSec = 120;
        };
      };

      systemd.timers.network-probe = {
        description = "Run network probe every 5 minutes";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "2min";
          OnUnitActiveSec = "5min";
          RandomizedDelaySec = "30s";
        };
      };

      systemd.services.network-monitor-sync = {
        description = "Sync sinnix-gw WAN monitor logs";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${syncScript}/bin/network-monitor-sync";
          TimeoutStartSec = 30;
        };
      };

      systemd.timers.network-monitor-sync = {
        description = "Sync sinnix-gw logs every 30 minutes";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "5min";
          OnUnitActiveSec = "30min";
          RandomizedDelaySec = "60s";
        };
      };
    };
} args
