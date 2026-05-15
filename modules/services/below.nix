# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored in /var/log/below (default).
# Retention is indefinite: at 1 s with dict-compress (chunk-32, ~8.8× over plain
# zstd) this is ~720 MB/day = ~260 GB/year. Without dict-compress: ~6.5 GB/day.
# Export via: below dump -O json/csv. Excluded from Borg in modules/backup.nix.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  pressureReporter = scriptPkgs.sinnix-observe;
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
      backoff = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Temporarily lower build/background runtime weights while PSI remains high.";
        };
        durationSec = lib.mkOption {
          type = lib.types.int;
          default = 120;
          description = "Minimum seconds to keep runtime backoff active after a pressure trigger.";
        };
        ioClearThresholdPct = lib.mkOption {
          type = lib.types.int;
          default = 3;
          description = "Consider I/O pressure clear when io.full avg10 is at or below this percentage.";
        };
        memoryClearThresholdPct = lib.mkOption {
          type = lib.types.int;
          default = 1;
          description = "Consider memory pressure clear when memory.full avg10 is at or below this percentage.";
        };
        clearSamples = lib.mkOption {
          type = lib.types.int;
          default = 3;
          description = "Consecutive clear samples required before restoring normal runtime weights.";
        };
        cpuWeight = lib.mkOption {
          type = lib.types.int;
          default = 1;
          description = "Runtime CPUWeight applied to developer/background slices during pressure backoff.";
        };
        ioWeight = lib.mkOption {
          type = lib.types.int;
          default = 1;
          description = "Runtime IOWeight applied to developer/background slices during pressure backoff.";
        };
        maintenanceCpuWeight = lib.mkOption {
          type = lib.types.int;
          default = 1;
          description = "Runtime CPUWeight applied to maintenance slices during pressure backoff.";
        };
        maintenanceIoWeight = lib.mkOption {
          type = lib.types.int;
          default = 1;
          description = "Runtime IOWeight applied to maintenance slices during pressure backoff.";
        };
      };
    };
  };
  configFn =
    {
      cfg,
      config,
      pkgs,
      ...
    }:
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
          # Fix D — observability tier. below.service was previously in
          # system.slice at default priority, which produced "data
          # collection took 938 ms" warnings under exactly the contention
          # below exists to capture. system-critical.slice provides high
          # CPU/IO weights and MemoryMin protection from reclaim.
          Slice = "system-critical.slice";
          Nice = -5;
          IOSchedulingClass = "best-effort";
          IOSchedulingPriority = 0;
        };
      };

      # The watchdog has two jobs: preserve forensic context through
      # sinnix-observe, and apply a reversible runtime backoff when PSI proves
      # opportunistic work is hurting the machine. This remains work-conserving:
      # it lowers build/background weights only during pressure instead of
      # keeping permanent CPU or bandwidth caps in the static slice policy.
      systemd.services.sinnix-pressure-watchdog = lib.mkIf cfg.pressureWatch.enable {
        path = with pkgs; [
          coreutils
          gawk
          systemd
          util-linux
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
            backoff_enabled=${if cfg.pressureWatch.backoff.enable then "1" else "0"}
            backoff_duration=${toString cfg.pressureWatch.backoff.durationSec}
            io_clear_threshold=${toString cfg.pressureWatch.backoff.ioClearThresholdPct}
            memory_clear_threshold=${toString cfg.pressureWatch.backoff.memoryClearThresholdPct}
            clear_samples_required=${toString cfg.pressureWatch.backoff.clearSamples}
            backoff_cpu_weight=${toString cfg.pressureWatch.backoff.cpuWeight}
            backoff_io_weight=${toString cfg.pressureWatch.backoff.ioWeight}
            maintenance_backoff_cpu_weight=${toString cfg.pressureWatch.backoff.maintenanceCpuWeight}
            maintenance_backoff_io_weight=${toString cfg.pressureWatch.backoff.maintenanceIoWeight}
            user_name=${lib.escapeShellArg config.sinnix.user.name}
            state_dir=/run/sinnix-pressure-watchdog
            last_report=0
            backoff_active=0
            backoff_until=0
            clear_seen=0
            mkdir -p "$state_dir"

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

            log_line() {
              local priority="$1"
              shift
              printf '%s\n' "$*" | systemd-cat -t sinnix-pressure-watchdog -p "$priority"
            }

            policy_key() {
              printf '%s_%s' "$1" "$2" | tr '/:@ ' '____'
            }

            user_systemctl_env() {
              local uid
              uid="$(id -u "$user_name" 2>/dev/null || true)"
              [ -n "$uid" ] || return 1
              [ -S "/run/user/$uid/bus" ] || return 1
              runuser -u "$user_name" -- \
                env XDG_RUNTIME_DIR="/run/user/$uid" \
                DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
                systemctl --user "$@"
            }

            manager_systemctl() {
              local manager="$1"
              shift
              if [ "$manager" = "user" ]; then
                user_systemctl_env "$@"
              else
                systemctl "$@"
              fi
            }

            unit_load_state() {
              local manager="$1"
              local unit="$2"
              manager_systemctl "$manager" show "$unit" -p LoadState --value 2>/dev/null || true
            }

            unit_property() {
              local manager="$1"
              local unit="$2"
              local property="$3"
              manager_systemctl "$manager" show "$unit" -p "$property" --value 2>/dev/null || true
            }

            save_policy() {
              local manager="$1"
              local unit="$2"
              local key file state cpu_weight io_weight
              key="$(policy_key "$manager" "$unit")"
              file="$state_dir/$key.policy"
              [ -e "$file" ] && return 0
              state="$(unit_load_state "$manager" "$unit")"
              [ -n "$state" ] && [ "$state" != "not-found" ] || return 0
              cpu_weight="$(unit_property "$manager" "$unit" CPUWeight)"
              io_weight="$(unit_property "$manager" "$unit" IOWeight)"
              {
                printf 'manager=%q\n' "$manager"
                printf 'unit=%q\n' "$unit"
                printf 'CPUWeight=%q\n' "$cpu_weight"
                printf 'IOWeight=%q\n' "$io_weight"
              } > "$file"
            }

            set_policy() {
              local manager="$1"
              local unit="$2"
              shift 2
              local state
              state="$(unit_load_state "$manager" "$unit")"
              [ -n "$state" ] && [ "$state" != "not-found" ] || return 0
              manager_systemctl "$manager" set-property --runtime "$unit" "$@" >/dev/null 2>&1 || true
            }

            apply_backoff_unit() {
              local manager="$1"
              local unit="$2"
              local cpu_weight="$3"
              local io_weight="$4"
              save_policy "$manager" "$unit"
              set_policy "$manager" "$unit" \
                "CPUWeight=$cpu_weight" \
                "IOWeight=$io_weight"
            }

            apply_backoff() {
              local unit
              for unit in nix.slice nix-build.slice background.slice; do
                apply_backoff_unit system "$unit" "$backoff_cpu_weight" "$backoff_io_weight"
              done
              for unit in sinnix.slice sinnix-maintenance.slice; do
                apply_backoff_unit system "$unit" "$maintenance_backoff_cpu_weight" "$maintenance_backoff_io_weight"
              done
              for unit in build.slice background.slice; do
                apply_backoff_unit user "$unit" "$backoff_cpu_weight" "$backoff_io_weight"
              done
              backoff_active=1
              touch "$state_dir/active"
              log_line notice "applied PSI runtime backoff: developer CPUWeight=$backoff_cpu_weight IOWeight=$backoff_io_weight; maintenance CPUWeight=$maintenance_backoff_cpu_weight IOWeight=$maintenance_backoff_io_weight"
            }

            restore_backoff() {
              local file manager unit cpu_weight io_weight
              for file in "$state_dir"/*.policy; do
                [ -e "$file" ] || continue
                manager=
                unit=
                CPUWeight=
                IOWeight=
                # shellcheck disable=SC1090
                . "$file"
                manager="''${manager:-}"
                unit="''${unit:-}"
                cpu_weight="''${CPUWeight:-}"
                io_weight="''${IOWeight:-}"
                [ -n "$manager" ] && [ -n "$unit" ] || continue
                set_policy "$manager" "$unit" \
                  "CPUWeight=''${cpu_weight:-100}" \
                  "IOWeight=''${io_weight:-100}"
                rm -f "$file"
              done
              rm -f "$state_dir/active"
              backoff_active=0
              clear_seen=0
              log_line notice "restored PSI runtime backoff"
            }

            cleanup_backoff() {
              if [ "$backoff_active" -eq 1 ]; then
                restore_backoff
              fi
            }

            terminate_watchdog() {
              cleanup_backoff
              exit 0
            }

            if [ -e "$state_dir/active" ]; then
              backoff_active=1
              restore_backoff
            fi
            trap cleanup_backoff EXIT
            trap terminate_watchdog INT TERM

            while true; do
              io_full="$(psi_avg10 full /proc/pressure/io)"
              memory_full="$(psi_avg10 full /proc/pressure/memory)"
              io_full="''${io_full:-0}"
              memory_full="''${memory_full:-0}"
              now="$(${pkgs.coreutils}/bin/date +%s)"

              pressure_tripped=0
              if [ "$io_full" -ge "$io_threshold" ] || [ "$memory_full" -ge "$memory_threshold" ]; then
                pressure_tripped=1
              fi

              if [ "$pressure_tripped" -eq 1 ]; then
                if [ "$backoff_enabled" -eq 1 ]; then
                  if [ "$backoff_active" -eq 0 ]; then
                    apply_backoff
                  fi
                  backoff_until=$((now + backoff_duration))
                  clear_seen=0
                fi

                if [ $((now - last_report)) -ge "$cooldown" ]; then
                  last_report="$now"
                  ${pressureReporter}/bin/sinnix-observe --format human --since "2 min ago" --duration "60 sec" --limit 8 \
                    | ${pkgs.systemd}/bin/systemd-cat -t sinnix-pressure-watchdog -p warning
                fi
              elif [ "$backoff_active" -eq 1 ]; then
                if [ "$io_full" -le "$io_clear_threshold" ] && [ "$memory_full" -le "$memory_clear_threshold" ]; then
                  clear_seen=$((clear_seen + 1))
                else
                  clear_seen=0
                fi

                if [ "$now" -ge "$backoff_until" ] && [ "$clear_seen" -ge "$clear_samples_required" ]; then
                  restore_backoff
                fi
              fi

              sleep "$interval"
            done
          ''}";
          Restart = "always";
          RestartSec = "5s";
        };
      };

    };
} args
