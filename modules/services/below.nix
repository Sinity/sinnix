# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored in /var/log/below (default).
# Storage: ~720 MB/day at 1s interval with dict-compress (chunk-32, ~8.8x over plain zstd).
# Without dict-compress: ~6.5 GB/day (plain zstd gets ~10x on raw CBOR, but
# dict-compress learns the repeated field-name strings across frames for another ~9x).
# Export via: below dump -O json/csv
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
let
  pressureReporter = pkgs.writeShellApplication {
    name = "sinnix-pressure-report";
    runtimeInputs = with pkgs; [
      below
      coreutils
      gawk
      gnugrep
      gnused
      procps
      systemd
    ];
    text = ''
      set -euo pipefail

      WINDOW="''${1:-2 min ago}"
      DURATION="''${2:-60 sec}"
      export HOME="''${HOME:-/var/log/below/home}"
      export XDG_CACHE_HOME="''${XDG_CACHE_HOME:-/var/log/below/cache}"
      export XDG_STATE_HOME="''${XDG_STATE_HOME:-/var/log/below/state}"

      summarize_process_io() {
        below dump process \
          -b "$WINDOW" \
          --duration "$DURATION" \
          -f datetime pid comm state io.rwbytes_per_sec mem.rss_bytes cmdline \
          -O tsv \
          --raw \
          --disable-title 2>/dev/null \
          | awk -F '\t' '
              NF >= 7 && $5 != "?" {
                key = $2
                value = $5 + 0
                if (!(key in max) || value > max[key]) {
                  max[key] = value
                  line[key] = $1 "\t" $2 "\t" $3 "\t" $4 "\t" $6 "\t" substr($7, 1, 180)
                }
              }
              END {
                for (key in max) print max[key] "\t" line[key]
              }
            ' \
          | sort -nr \
          | awk -F '\t' '
              BEGIN { print "max_rw_Bps\tdatetime\tpid\tcomm\tstate\trss_B\tcmd" }
              NR <= 8 { print }
            '
      }

      summarize_cgroup_pressure() {
        below dump cgroup \
          -b "$WINDOW" \
          --duration "$DURATION" \
          -f datetime name pressure.io_full_pct pressure.memory_full_pct io.rwbytes_per_sec mem.total \
          -O tsv \
          --raw \
          --disable-title 2>/dev/null \
          | awk -F '\t' '
              NF >= 6 {
                key = $2
                io_full = ($3 == "" || $3 == "?" ? 0 : $3 + 0)
                rw = ($5 == "" || $5 == "?" ? 0 : $5 + 0)
                if (!(key in max_pressure) || io_full > max_pressure[key] || rw > max_rw[key]) {
                  max_pressure[key] = io_full
                  max_rw[key] = rw
                  line[key] = $1 "\t" $2 "\t" $4 "\t" max_rw[key] "\t" $6
                }
              }
              END {
                for (key in max_pressure) print max_pressure[key] "\t" line[key]
              }
            ' \
          | sort -nr \
          | awk -F '\t' '
              BEGIN { print "max_io_full_pct\tdatetime\tcgroup\tmemory_full_pct\trw_Bps\tmem_B" }
              NR <= 8 { print }
            '
      }

      echo "=== pressure snapshot $(date --iso-8601=seconds) ==="
      echo "--- /proc/pressure ---"
      printf 'cpu '; cat /proc/pressure/cpu
      printf 'memory '; cat /proc/pressure/memory
      printf 'io '; cat /proc/pressure/io
      echo

      echo "--- memory ---"
      free -h
      echo

      echo "--- blocked tasks ---"
      ps -eo pid,ppid,stat,wchan:24,comm,cmd | awk '$3 ~ /D/ || NR == 1' | sed -n '1,40p'
      echo

      echo "--- below: top recent processes by I/O ---"
      summarize_process_io || true
      echo

      echo "--- below: top recent cgroups by I/O pressure ---"
      summarize_cgroup_pressure || true
    '';
  };
in
mkServiceModule {
  name = "below";
  description = "below time-traveling resource monitor";
  health = {
    unit = "below.service";
    type = "service";
    restartable = true;
  };
  extraOptions = {
    collectIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Collection interval in seconds.";
    };
    retentionDays = lib.mkOption {
      type = lib.types.int;
      default = 14;
      description = "Number of days of below store chunks to retain.";
    };
    pressureWatch = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Emit automatic below-backed reports when PSI crosses thresholds.";
      };
      intervalSec = lib.mkOption {
        type = lib.types.int;
        default = 10;
        description = "Pressure sampling interval in seconds.";
      };
      ioFullThresholdPct = lib.mkOption {
        type = lib.types.int;
        default = 10;
        description = "Report when io.full avg10 is at or above this percentage.";
      };
      memoryFullThresholdPct = lib.mkOption {
        type = lib.types.int;
        default = 5;
        description = "Report when memory.full avg10 is at or above this percentage.";
      };
      cooldownSec = lib.mkOption {
        type = lib.types.int;
        default = 300;
        description = "Minimum seconds between automatic pressure reports.";
      };
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    {
      environment.systemPackages = [
        pkgs.below
        pressureReporter
      ];

      # /var/log/below/store is the below data directory. Create it via tmpfiles
      # so below.service can start even if the /persist bind-mount hasn't activated
      # yet (e.g. first boot without @blank). When impermanence is active, the
      # bind-mount overlays this and persists the data across reboots.
      systemd.tmpfiles.rules = [
        "d /var/log/below 0755 root root -"
        "d /var/log/below/store 0755 root root -"
        "d /var/log/below/home 0755 root root -"
        "d /var/log/below/cache 0755 root root -"
        "d /var/log/below/state 0755 root root -"
      ];

      systemd.services.below = {
        description = "below - Time traveling resource monitor";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];

        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.below}/bin/below record --collect-io-stat --compress --dict-compress-chunk-size 32 --interval-s ${toString cfg.collectIntervalSec}";
          Restart = "on-failure";
          RestartSec = "5s";
        };
      };

      systemd.services.sinnix-pressure-watchdog = lib.mkIf cfg.pressureWatch.enable {
        path = with pkgs; [
          coreutils
          gawk
          systemd
        ];
        description = "Report system pressure incidents with below attribution";
        wantedBy = [ "multi-user.target" ];
        after = [ "below.service" ];
        wants = [ "below.service" ];
        serviceConfig = {
          Type = "simple";
          Nice = 19;
          IOSchedulingClass = "idle";
          Environment = [
            "HOME=/var/log/below/home"
            "XDG_CACHE_HOME=/var/log/below/cache"
            "XDG_STATE_HOME=/var/log/below/state"
          ];
          ExecStart = "${pkgs.writeShellScript "sinnix-pressure-watchdog" ''
            set -euo pipefail

            interval=${toString cfg.pressureWatch.intervalSec}
            io_threshold=${toString cfg.pressureWatch.ioFullThresholdPct}
            memory_threshold=${toString cfg.pressureWatch.memoryFullThresholdPct}
            cooldown=${toString cfg.pressureWatch.cooldownSec}
            last_report=0

            psi_avg10() {
              awk -v key="$1" '$1 == "full" {
                for (i = 1; i <= NF; i++) {
                  if ($i ~ /^avg10=/) {
                    split($i, a, "=")
                    print int(a[2])
                    exit
                  }
                }
              }' "$2"
            }

            while true; do
              io_full="$(psi_avg10 full /proc/pressure/io)"
              memory_full="$(psi_avg10 full /proc/pressure/memory)"
              now="$(${pkgs.coreutils}/bin/date +%s)"

              if { [ "$io_full" -ge "$io_threshold" ] || [ "$memory_full" -ge "$memory_threshold" ]; } \
                && [ $((now - last_report)) -ge "$cooldown" ]; then
                last_report="$now"
                ${pressureReporter}/bin/sinnix-pressure-report "2 min ago" "60 sec" \
                  | ${pkgs.systemd}/bin/systemd-cat -t sinnix-pressure-watchdog -p warning
              fi

              sleep "$interval"
            done
          ''}";
          Restart = "always";
          RestartSec = "5s";
        };
      };

      systemd.services.below-prune = {
        description = "Prune old below resource monitor chunks";
        serviceConfig = {
          Type = "oneshot";
          Nice = 19;
          IOSchedulingClass = "idle";
          ExecStart = pkgs.writeShellScript "below-prune" ''
            set -euo pipefail
            [ -d /var/log/below/store ] || exit 0
            ${pkgs.findutils}/bin/find /var/log/below/store -xdev -type f -mtime +${toString cfg.retentionDays} -delete
          '';
        };
      };

      systemd.timers.below-prune = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "daily";
          Persistent = false;
          RandomizedDelaySec = "30m";
        };
      };

    };
} args
