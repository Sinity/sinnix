# OpenWrt router configuration builder
#
# Produces:
#   packages.x86_64-linux.router-config  — derivation with configure.sh + install-packages.sh + health-check.sh
#   apps.x86_64-linux.router-deploy      — `nix run .#router-deploy` to push & apply
#   apps.x86_64-linux.router-shell       — `nix run .#router-shell` to open an SSH shell
#   apps.x86_64-linux.router-health      — `nix run .#router-health` to run health checks
#
# Usage:
#   nix run .#router-deploy               # full deployment (backup + packages + config + health check)
#   nix run .#router-deploy -- --dry-run   # print scripts without applying
#   nix run .#router-shell                 # SSH shell into the router
#   nix run .#router-health                # verify router health post-deploy

{ inputs, ... }:
{
  perSystem =
    { pkgs, lib, ... }:
    let
      # Load the openwrt library
      openwrtLib = import ../modules/lib/openwrt.nix { inherit lib; };

      # Load router config
      routerCfg = import ../hosts/sinnix-gw/default.nix { inherit lib; };

      # Build the UCI apply script (fragment — no shebang, no set)
      uciScript = openwrtLib.mkUciScript routerCfg.uci;

      # Build the opkg install script (standalone — has shebang + set -eu)
      pkgScript = openwrtLib.mkOpkgScript routerCfg.packages;

      # ─────────────────────────────────────────────────────────────
      # configure.sh — runs ON the router (ash, no pipefail)
      # ─────────────────────────────────────────────────────────────
      configureScript = ''
        #!/bin/sh
        # sinnix-gw full configuration script
        # Auto-generated — do not edit manually. Edit hosts/sinnix-gw/default.nix instead.
        set -eu

        echo "=== sinnix-gw router configuration ==="
        echo ""

        # ── Clean up OpenWrt default anonymous sections ──
        # OpenWrt ships anonymous firewall zones/rules that conflict with our named ones.
        # Delete all anonymous sections first so our named config is authoritative.
        echo "Cleaning up anonymous firewall sections..."
        while uci -q get firewall.@zone[-1] >/dev/null 2>&1; do
          uci -q delete firewall.@zone[-1]
        done
        while uci -q get firewall.@defaults[-1] >/dev/null 2>&1; do
          uci -q delete firewall.@defaults[-1]
        done
        while uci -q get firewall.@forwarding[-1] >/dev/null 2>&1; do
          uci -q delete firewall.@forwarding[-1]
        done
        while uci -q get firewall.@rule[-1] >/dev/null 2>&1; do
          uci -q delete firewall.@rule[-1]
        done
        while uci -q get firewall.@redirect[-1] >/dev/null 2>&1; do
          uci -q delete firewall.@redirect[-1]
        done
        uci commit firewall
        echo "✓ Anonymous firewall sections cleared."

        # ── UCI configuration ──
        echo "[ 1/2 ] Applying UCI configuration..."
        ${uciScript}

        # ── Post-UCI setup ──
        echo "[ 2/2 ] Running post-configuration steps..."
        ${routerCfg.postCommands}

        echo ""
        echo "=== sinnix-gw configuration applied ==="
      '';

      # ─────────────────────────────────────────────────────────────
      # health-check.sh — runs ON the router (ash, no pipefail)
      # ─────────────────────────────────────────────────────────────
      healthCheckScript = ''
        #!/bin/sh
        # sinnix-gw health check — verifies router is correctly configured
        set -eu

        PASS=0; FAIL=0; WARN=0

        check_pass() { echo "  ✓ PASS  $1"; PASS=$((PASS + 1)); }
        check_fail() { echo "  ✗ FAIL  $1"; FAIL=$((FAIL + 1)); }
        check_warn() { echo "  ⚠ WARN  $1"; WARN=$((WARN + 1)); }

        echo "=== sinnix-gw health check ==="
        echo ""

        # ── Hostname ──
        HOSTNAME=$(uci -q get system.system.hostname 2>/dev/null || echo "")
        if [ "$HOSTNAME" = "sinnix-gw" ]; then
          check_pass "Hostname: sinnix-gw"
        else
          check_fail "Hostname: expected sinnix-gw, got '$HOSTNAME'"
        fi

        # ── Network interfaces ──
        echo ""
        echo "Network:"
        if ip link show br-lan >/dev/null 2>&1; then
          check_pass "br-lan interface exists"
        else
          check_fail "br-lan interface missing"
        fi

        if ip link show wan >/dev/null 2>&1; then
          check_pass "wan interface exists"
        else
          check_fail "wan interface missing"
        fi

        WAN_IP=$(ip -4 addr show wan 2>/dev/null | grep -o 'inet [0-9.]*' | cut -d' ' -f2 || echo "")
        if [ -n "$WAN_IP" ]; then
          check_pass "WAN IP: $WAN_IP"
        else
          check_fail "WAN has no IPv4 address"
        fi

        # ── WAN connectivity ──
        echo ""
        echo "Connectivity:"
        if ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1; then
          check_pass "WAN connectivity (ping 1.1.1.1)"
        else
          check_fail "WAN connectivity (ping 1.1.1.1 failed)"
        fi

        # ── DNS resolution ──
        echo ""
        echo "DNS:"
        if nslookup example.com 127.0.0.1 >/dev/null 2>&1; then
          check_pass "DNS resolution via dnsmasq"
        else
          check_fail "DNS resolution via dnsmasq"
        fi

        if [ -f /etc/init.d/https-dns-proxy ]; then
          if pidof https-dns-proxy >/dev/null 2>&1 || pidof https_dns_proxy >/dev/null 2>&1; then
            check_pass "https-dns-proxy (DoH) running"
          else
            check_fail "https-dns-proxy (DoH) not running"
          fi
        else
          check_warn "https-dns-proxy not installed"
        fi

        # ── WiFi ──
        echo ""
        echo "WiFi:"
        RADIO0_DISABLED=$(uci -q get wireless.radio0.disabled 2>/dev/null || echo "1")
        if [ "$RADIO0_DISABLED" = "0" ]; then
          SSID0=$(uci -q get wireless.default_radio0.ssid 2>/dev/null || echo "?")
          check_pass "radio0 (2.4GHz) enabled — SSID: $SSID0"
        else
          check_fail "radio0 (2.4GHz) disabled"
        fi

        RADIO1_DISABLED=$(uci -q get wireless.radio1.disabled 2>/dev/null || echo "1")
        if [ "$RADIO1_DISABLED" = "0" ]; then
          SSID1=$(uci -q get wireless.default_radio1.ssid 2>/dev/null || echo "?")
          check_pass "radio1 (5GHz) enabled — SSID: $SSID1"
        else
          check_fail "radio1 (5GHz) disabled"
        fi

        # ── Services ──
        echo ""
        echo "Services:"

        # SQM: not a daemon — check if qdisc is active
        if tc qdisc show dev wan 2>/dev/null | grep -q fq_codel; then
          check_pass "SQM (fq_codel on wan)"
        else
          check_warn "SQM: fq_codel not active on wan"
        fi

        # Daemon services
        for svc in miniupnpd nlbwmon irqbalance; do
          if [ -f "/etc/init.d/$svc" ]; then
            if pidof "$svc" >/dev/null 2>&1; then
              check_pass "$svc running"
            else
              check_warn "$svc installed but not running"
            fi
          else
            check_warn "$svc not installed"
          fi
        done

        # adblock-fast: DNS-level ad blocking
        if [ -x /etc/init.d/adblock-fast ]; then
          if /etc/init.d/adblock-fast enabled 2>/dev/null; then
            check_pass "adblock-fast enabled"
          else
            check_warn "adblock-fast installed but not enabled"
          fi
        else
          check_warn "adblock-fast not installed"
        fi

        # ── SSH key ──
        echo ""
        echo "Security:"
        AUTHKEYS="/etc/dropbear/authorized_keys"
        if [ -f "$AUTHKEYS" ] && grep -qF "sinity@sinnix-prime" "$AUTHKEYS" 2>/dev/null; then
          check_pass "SSH authorized key deployed"
        else
          check_fail "SSH authorized key missing"
        fi

        # ── Sysctl tuning ──
        echo ""
        echo "Kernel tuning:"
        CONNTRACK=$(cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || echo "0")
        if [ "$CONNTRACK" -ge 32768 ] 2>/dev/null; then
          check_pass "nf_conntrack_max = $CONNTRACK"
        else
          check_warn "nf_conntrack_max = $CONNTRACK (expected >= 32768)"
        fi

        TCP_FO=$(cat /proc/sys/net/ipv4/tcp_fastopen 2>/dev/null || echo "0")
        if [ "$TCP_FO" = "3" ]; then
          check_pass "tcp_fastopen = 3"
        else
          check_warn "tcp_fastopen = $TCP_FO (expected 3)"
        fi

        # ── Summary ──
        echo ""
        echo "════════════════════════════════════════"
        echo "  Results: $PASS passed, $FAIL failed, $WARN warnings"
        echo "════════════════════════════════════════"

        if [ "$FAIL" -gt 0 ]; then
          echo ""
          echo "Some checks failed. Review output above."
          exit 1
        fi
      '';

      # ─────────────────────────────────────────────────────────────
      # router-config package: derivation containing all deploy scripts
      # ─────────────────────────────────────────────────────────────
      routerConfigDrv = pkgs.runCommand "sinnix-gw-config" { } ''
        mkdir -p $out
        cat > $out/configure.sh << 'CONFIGURE_EOF'
        ${configureScript}
        CONFIGURE_EOF
        chmod +x $out/configure.sh

        cat > $out/install-packages.sh << 'PKG_EOF'
        ${pkgScript}
        PKG_EOF
        chmod +x $out/install-packages.sh

        cat > $out/health-check.sh << 'HEALTH_EOF'
        ${healthCheckScript}
        HEALTH_EOF
        chmod +x $out/health-check.sh

        # Human-readable diff-friendly UCI dump for review
        cat > $out/uci-commands.txt << 'UCI_EOF'
        # UCI commands that will be applied by configure.sh
        ${uciScript}
        UCI_EOF
      '';

      # ─────────────────────────────────────────────────────────────
      # Shared SSH/SCP connection setup (reused by deploy + health)
      # Sets SSH_CMD, SCP_CMD, ROUTER_ADDR, ROUTER_USER, ROUTER_PASS
      # ─────────────────────────────────────────────────────────────
      sshSetupFragment = ''
        ROUTER_ADDR="${routerCfg.address}"
        ROUTER_USER="${routerCfg.sshUser}"
        ROUTER_PASS=""

        SSH_BASE_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
        SSH_KEY_CMD="${pkgs.openssh}/bin/ssh $SSH_BASE_OPTS -o BatchMode=yes"
        SCP_KEY_CMD="${pkgs.openssh}/bin/scp $SSH_BASE_OPTS -o BatchMode=yes"

        # Test key-based auth first, fall back to password
        if $SSH_KEY_CMD ''${ROUTER_USER}@''${ROUTER_ADDR} 'echo ok' >/dev/null 2>&1; then
          echo "✓ Connecting with key-based auth..."
          SSH_CMD="$SSH_KEY_CMD"
          SCP_CMD="$SCP_KEY_CMD"
        else
          echo "Key auth failed — falling back to password."
          echo -n "Router password (''${ROUTER_USER}@''${ROUTER_ADDR}): "
          read -rs ROUTER_PASS
          echo ""
          SSH_CMD="${pkgs.sshpass}/bin/sshpass -p \"$ROUTER_PASS\" ${pkgs.openssh}/bin/ssh $SSH_BASE_OPTS -o PreferredAuthentications=password -o PubkeyAuthentication=no"
          SCP_CMD="${pkgs.sshpass}/bin/sshpass -p \"$ROUTER_PASS\" ${pkgs.openssh}/bin/scp $SSH_BASE_OPTS -o PreferredAuthentications=password -o PubkeyAuthentication=no"
        fi
      '';

      # ─────────────────────────────────────────────────────────────
      # deploy script: orchestrates the full SSH push
      # ─────────────────────────────────────────────────────────────
      deployScript = pkgs.writeShellScriptBin "router-deploy" ''
        set -euo pipefail

        ORIG_CONFIG_DIR="${routerConfigDrv}"
        DRY_RUN=0
        WIFI_PSK_FILE="/run/agenix/wifi-psk"

        # Parse args
        for arg in "$@"; do
          case "$arg" in
            --dry-run|-n)
              DRY_RUN=1
              ;;
            --help|-h)
              echo "Usage: nix run .#router-deploy [--dry-run]"
              echo ""
              echo "Deploys sinnix-gw router configuration via SSH."
              echo "Router: ${routerCfg.sshUser}@${routerCfg.address}"
              echo ""
              echo "Options:"
              echo "  --dry-run   Print scripts without executing on router"
              exit 0
              ;;
          esac
        done

        # ── Inject WiFi PSK from agenix secret ──
        CONFIG_DIR=$(mktemp -d)
        trap 'rm -rf "$CONFIG_DIR"' EXIT
        cp "$ORIG_CONFIG_DIR"/* "$CONFIG_DIR/"
        chmod u+w "$CONFIG_DIR"/*

        if [ -f "$WIFI_PSK_FILE" ]; then
          WIFI_PSK=$(cat "$WIFI_PSK_FILE")
          ${pkgs.gnused}/bin/sed -i "s|@@WIFI_PSK@@|$WIFI_PSK|g" "$CONFIG_DIR/configure.sh"
          echo "✓ WiFi PSK injected from agenix secret"
        else
          echo "⚠  $WIFI_PSK_FILE not found — WiFi PSK will be a placeholder."
          echo "   Create it: echo -n 'your-psk' | agenix -e secret/wifi-psk.age"
        fi

        if [ "$DRY_RUN" -eq 1 ]; then
          echo "=== DRY RUN: scripts that would be applied ==="
          echo ""
          echo "--- install-packages.sh ---"
          cat "$CONFIG_DIR/install-packages.sh"
          echo ""
          echo "--- configure.sh ---"
          cat "$CONFIG_DIR/configure.sh"
          echo ""
          echo "--- health-check.sh ---"
          cat "$CONFIG_DIR/health-check.sh"
          exit 0
        fi

        ${sshSetupFragment}

        REMOTE="''${ROUTER_USER}@''${ROUTER_ADDR}"

        # ── Step 0: Backup existing config ──
        echo ""
        echo "[ 0/4 ] Backing up router config..."
        BACKUP_DIR="$HOME/.cache/sinnix-gw-backups"
        mkdir -p "$BACKUP_DIR"
        BACKUP_NAME="$(date +%Y%m%d-%H%M%S).tar.gz"
        $SSH_CMD "$REMOTE" 'tar czf /tmp/sinnix-gw-backup.tar.gz -C / etc/config 2>/dev/null || echo "(no existing config to backup)"'
        if $SCP_CMD "$REMOTE:/tmp/sinnix-gw-backup.tar.gz" "$BACKUP_DIR/$BACKUP_NAME" 2>/dev/null; then
          echo "✓ Config backed up to $BACKUP_DIR/$BACKUP_NAME"
        else
          echo "⚠  No existing config to backup (fresh install?)"
        fi
        $SSH_CMD "$REMOTE" 'rm -f /tmp/sinnix-gw-backup.tar.gz' 2>/dev/null || true

        # ── Step 1: Upload scripts to router via SCP ──
        echo ""
        echo "[ 1/4 ] Uploading scripts to ''${ROUTER_ADDR}..."
        $SCP_CMD "$CONFIG_DIR/install-packages.sh" "$CONFIG_DIR/configure.sh" "$CONFIG_DIR/health-check.sh" "$REMOTE:/tmp/"

        # ── Step 2: Install packages ──
        echo ""
        echo "[ 2/4 ] Installing opkg packages..."
        $SSH_CMD "$REMOTE" 'sh /tmp/install-packages.sh'

        # ── Step 3: Apply UCI + post-setup ──
        echo ""
        echo "[ 3/4 ] Applying router configuration..."
        $SSH_CMD "$REMOTE" 'sh /tmp/configure.sh'

        # Give services a moment to settle after network reload
        echo ""
        echo "Waiting for services to settle..."
        sleep 5

        # ── Step 4: Health check ──
        echo ""
        echo "[ 4/4 ] Running health check..."
        # Reconnect fresh — network config may have changed during step 3
        if ${pkgs.openssh}/bin/ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o BatchMode=yes \
            ''${ROUTER_USER}@''${ROUTER_ADDR} 'sh /tmp/health-check.sh'; then
          echo ""
          echo "✓ Health check passed."
        else
          # Key auth may not work yet if this is first deploy; retry with password
          if [ -n "$ROUTER_PASS" ]; then
            ${pkgs.sshpass}/bin/sshpass -p "$ROUTER_PASS" \
              ${pkgs.openssh}/bin/ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 \
              -o PreferredAuthentications=password -o PubkeyAuthentication=no \
              ''${ROUTER_USER}@''${ROUTER_ADDR} 'sh /tmp/health-check.sh' || true
          else
            echo "⚠  Could not reconnect for health check. Try manually:"
            echo "   ssh root@''${ROUTER_ADDR} 'sh /tmp/health-check.sh'"
          fi
        fi

        # Cleanup temp scripts
        $SSH_CMD "$REMOTE" 'rm -f /tmp/install-packages.sh /tmp/configure.sh /tmp/health-check.sh' 2>/dev/null || true

        echo ""
        echo "╔══════════════════════════════════════════════════════╗"
        echo "║  sinnix-gw deployment complete!                      ║"
        echo "║  Router: ''${ROUTER_ADDR}  (sinnix-gw.lan)            ║"
        echo "║  SSH:    ssh root@sinnix-gw.lan                      ║"
        echo "║  Admin:  http://''${ROUTER_ADDR} (LuCI)               ║"
        echo "╚══════════════════════════════════════════════════════╝"
      '';

      # ─────────────────────────────────────────────────────────────
      # health check script: run health checks independently
      # ─────────────────────────────────────────────────────────────
      routerHealth = pkgs.writeShellScriptBin "router-health" ''
        set -euo pipefail

        CONFIG_DIR="${routerConfigDrv}"

        ${sshSetupFragment}

        REMOTE="''${ROUTER_USER}@''${ROUTER_ADDR}"

        echo "Uploading health check to ''${ROUTER_ADDR}..."
        $SCP_CMD "$CONFIG_DIR/health-check.sh" "$REMOTE:/tmp/"
        $SSH_CMD "$REMOTE" 'sh /tmp/health-check.sh'
        $SSH_CMD "$REMOTE" 'rm -f /tmp/health-check.sh' 2>/dev/null || true
      '';

      # ─────────────────────────────────────────────────────────────
      # shell script: quick SSH access to router
      # ─────────────────────────────────────────────────────────────
      routerShell = pkgs.writeShellScriptBin "router-shell" ''
        set -euo pipefail
        ROUTER_ADDR="${routerCfg.address}"
        ROUTER_USER="${routerCfg.sshUser}"
        SSH_OPTS="-o StrictHostKeyChecking=accept-new"

        # Try key auth first
        if ${pkgs.openssh}/bin/ssh $SSH_OPTS -o BatchMode=yes -o ConnectTimeout=5 \
            ''${ROUTER_USER}@''${ROUTER_ADDR} 'echo ok' >/dev/null 2>&1; then
          exec ${pkgs.openssh}/bin/ssh $SSH_OPTS ''${ROUTER_USER}@''${ROUTER_ADDR}
        else
          echo "Using password auth (key not yet installed)."
          echo -n "Router password (''${ROUTER_USER}@''${ROUTER_ADDR}): "
          read -rs ROUTER_PASS
          echo ""
          exec ${pkgs.sshpass}/bin/sshpass -p "$ROUTER_PASS" \
            ${pkgs.openssh}/bin/ssh $SSH_OPTS \
            -o PreferredAuthentications=password -o PubkeyAuthentication=no \
            ''${ROUTER_USER}@''${ROUTER_ADDR}
        fi
      '';

    in
    {
      packages = {
        router-config = routerConfigDrv;
      };

      apps = {
        router-deploy = {
          type = "app";
          program = "${deployScript}/bin/router-deploy";
          meta.description = "Deploy sinnix-gw OpenWrt configuration via SSH";
        };

        router-shell = {
          type = "app";
          program = "${routerShell}/bin/router-shell";
          meta.description = "Open SSH shell on sinnix-gw router";
        };

        router-health = {
          type = "app";
          program = "${routerHealth}/bin/router-health";
          meta.description = "Run health checks on sinnix-gw router";
        };
      };
    };
}
