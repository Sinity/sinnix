# System diagnostics and introspection tools
#
# Provides:
# - Hardware introspection (hwinfo, lshw, smartmontools)
# - Performance analysis (machine-experiment-run, hogkill, asbl-no-moar)
# - Boot metrics capture (systemd-analyze, dmesg)
# - Persistent journald logging with compression
{
  pkgs,
  lib,
  config,
  inputs,
  helpers,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  inherit (config.sinnix.paths) capturesRoot;
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  journaldBaseDir = "${capturesRoot}/syslog";
  bootMetricsDir = "${journaldBaseDir}/boot-metrics";

  coreDiagnostics = with pkgs; [
    hwinfo
    inxi
    lshw
    smartmontools
    nvme-cli
    hdparm
  ];

  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = with pkgs; [
      coreutils
      findutils
      util-linux
      systemd
    ];
    text = ''
      set -euo pipefail
      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
      OUT_DIR="${bootMetricsDir}/$BOOT_ID"
      mkdir -p "$OUT_DIR"
      systemd-analyze time > "$OUT_DIR/time.txt"
      systemd-analyze blame > "$OUT_DIR/blame.txt"
      journalctl -b -p 0..3 > "$OUT_DIR/journal-errors.log"
      dmesg > "$OUT_DIR/dmesg.log"
    '';
  };

  resourceAudit = pkgs.writeShellApplication {
    name = "sinnix-resource-audit";
    runtimeInputs = with pkgs; [
      coreutils
      gnugrep
      systemd
    ];
    text = ''
      set -euo pipefail

      failures=0

      fail() {
        echo "FAIL: $*" >&2
        failures=$((failures + 1))
      }

      pass() {
        echo "ok: $*"
      }

      prop() {
        systemctl show "$1" -P "$2" 2>/dev/null || true
      }

      require_eq() {
        local unit="$1"
        local key="$2"
        local expected="$3"
        local actual
        actual="$(prop "$unit" "$key")"
        if [ "$actual" = "$expected" ]; then
          pass "$unit $key=$actual"
        else
          fail "$unit $key expected $expected got ''${actual:-<empty>}"
        fi
      }

      require_contains() {
        local unit="$1"
        local key="$2"
        local needle="$3"
        local actual
        actual="$(prop "$unit" "$key")"
        if printf '%s\n' "$actual" | grep -Fq "$needle"; then
          pass "$unit $key contains $needle"
        else
          fail "$unit $key missing $needle; got ''${actual:-<empty>}"
        fi
      }

      require_active() {
        local unit="$1"
        if [ "$(systemctl is-active "$unit" 2>/dev/null || true)" = active ]; then
          pass "$unit active"
        else
          fail "$unit is not active"
        fi
      }

      require_active below.service
      require_eq below-prune.timer Persistent no
      require_eq btrbk.timer Persistent no
      require_eq borgbackup-job-realm.timer Persistent no
      require_eq borgbackup-job-persist.timer Persistent no

      echo
      echo "Current pressure:"
      cat /proc/pressure/memory
      cat /proc/pressure/io

      if [ "$failures" -gt 0 ]; then
        echo "$failures resource policy check(s) failed" >&2
        exit 1
      fi
    '';
  };
in
{
  config = {
    environment.systemPackages = lib.mkIf isDesktop (
      coreDiagnostics
      ++ [
        scriptPkgs.hogkill
        scriptPkgs.asbl-no-moar
        scriptPkgs.nuke-builds
        scriptPkgs.sinnix-observe
        scriptPkgs.machine-experiment-run
        scriptPkgs.syslog-index
        resourceAudit
      ]
    );

    # Logging and metrics (always on)
    # Note: owned by user since this is for boot-metrics capture, not journald itself
    systemd.tmpfiles.rules = [
      "d ${journaldBaseDir} 0750 ${username} users -"
      "d ${bootMetricsDir} 0750 ${username} users -"
      "d ${journaldBaseDir}/index 0750 ${username} users -"
    ];

    services.journald.extraConfig = ''
      # Storage configuration
      Storage=persistent
      Compress=yes

      # Corruption resilience: sync every 30s (default 5min), smaller files
      # On power loss, at most 30s of logs lost; corruption affects max 100MB
      SyncIntervalSec=30s
      SystemMaxFileSize=100M

      # Size limits: Large allocation for long-term retention
      SystemMaxUse=50G
      SystemKeepFree=10G

      # Time-based retention: DISABLED - size is the only limit
      MaxRetentionSec=0

      # Rotate files daily to limit blast radius of corruption
      MaxFileSec=1day

      # Rate limiting: aggressive limits to prevent spam
      RateLimitIntervalSec=30s
      RateLimitBurst=500

      # Forwarding to syslog disabled (we use journald native)
      ForwardToSyslog=no
    '';

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics";
      # Must wait for boot to fully complete — systemd-analyze requires
      # FinishTimestampMonotonic != 0, which is only set after all boot
      # services finish. With slow nofail mounts this can take 2+ min.
      after = [
        "systemd-journald.service"
        "multi-user.target"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
    };

    systemd.timers.capture-boot-metrics = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "3min";
        AccuracySec = "10s";
      };
    };

    systemd.services.syslog-index = {
      description = "Build no-loss syslog/journal capture indexes";
      after = [
        "local-fs.target"
        "systemd-journald.service"
      ];
      unitConfig.RequiresMountsFor = [ journaldBaseDir ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.syslog-index}/bin/syslog-index --no-edge-inspect";
      };
    };

    systemd.timers.syslog-index = {
      description = "Refresh no-loss syslog/journal capture indexes";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "4min";
        OnUnitActiveSec = "1h";
        AccuracySec = "1min";
      };
    };
  };
}
