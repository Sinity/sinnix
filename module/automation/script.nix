# Scripts

{ pkgs, ... }:
let
  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    set -euo pipefail

    if systemctl --user --quiet is-active waybar.service; then
      systemctl --user stop waybar.service
    else
      systemctl --user start waybar.service
    fi
  '';

  perfScan = pkgs.writeShellApplication {
    name = "perf-scan";
    runtimeInputs = with pkgs; [
      bash
      coreutils
      gawk
      gnugrep
      findutils
      procps
      util-linux
      inxi
      lm_sensors
      smartmontools
      nvme-cli
      sysbench
      stressapptest
      fio
      glmark2
      vkmark
      powertop
      sysstat
      bc
    ];
    text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            usage() {
              cat <<'EOF'
      perf-scan - system diagnostics and benchmarking helper

      Usage: perf-scan [--full] [--log-dir DIR]

        --full        run extended (longer) benchmarks in addition to the quick sweep
        --log-dir DIR write reports to DIR instead of $HOME/.cache/perf-scan

      Environment variables:
        PERF_SCAN_LOG_DIR   override the default report directory
        PERF_SCAN_MODE      same as --full when set to "full"

      Most storage and power checks need passwordless sudo access. If sudo
      credentials are required you will be prompted when the command runs.
      EOF
            }

            MODE="''${PERF_SCAN_MODE:-quick}"
            LOG_DIR_OVERRIDE=""

            while [[ $# -gt 0 ]]; do
              case "$1" in
                --full)
                  MODE="full"
                  shift
                  ;;
                --log-dir)
                  [[ $# -ge 2 ]] || { echo "--log-dir requires a path" >&2; exit 2; }
                  LOG_DIR_OVERRIDE="$2"
                  shift 2
                  ;;
                -h|--help)
                  usage
                  exit 0
                  ;;
                *)
                  echo "Unknown option: $1" >&2
                  usage >&2
                  exit 2
                  ;;
              esac
            done

            LOG_ROOT=''${LOG_DIR_OVERRIDE:-''${PERF_SCAN_LOG_DIR:-$HOME/.cache/perf-scan}}
            mkdir -p "$LOG_ROOT"
            timestamp=$(date +'%Y%m%d-%H%M%S')
            log_file="$LOG_ROOT/perf-scan-''${MODE}-''${timestamp}.log"

            scratch=$(mktemp -d "''${TMPDIR:-/tmp}/perf-scan.XXXXXX")
      cleanup() {
        printf '\nReports saved to: %s\n' "$log_file"
        printf 'Scratch data kept in: %s\n' "$scratch"
      }
            trap cleanup EXIT

            exec > >(tee "$log_file")
            exec 2>&1

            bold=""
            reset=""
            if command -v tput >/dev/null 2>&1; then
              bold=$(tput bold || true)
              reset=$(tput sgr0 || true)
            fi

            section() {
              printf "\n%s== %s ==%s\n" "$bold" "$1" "$reset"
            }

            bullet() {
              printf "  • %s\n" "$1"
            }

            run_cmd() {
              local label="$1"
              shift
              bullet "$label"
              set +e
              local output
              output="$("$@" 2>&1)"
              local status=$?
              set -e
              if [[ -n "$output" ]]; then
                printf '%s\n' "$output" | sed 's/^/    /'
              fi
              if [[ $status -ne 0 ]]; then
                printf '    ↪ command exited with %d\n' "$status"
              fi
            }

            run_stream() {
              local label="$1"
              shift
              bullet "$label"
              set +e
              "$@" 2>&1 | sed 's/^/    /'
              local status=''${PIPESTATUS[0]}
              set -e
              if [[ $status -ne 0 ]]; then
                printf '    ↪ command exited with %d\n' "$status"
              fi
            }

            have_cmd() {
              command -v "$1" >/dev/null 2>&1
            }

            run_if_exists() {
              local label="$1"
              shift
              if have_cmd "$1"; then
                run_stream "$label" "$@"
              else
                bullet "$label (tool not available: $1)"
              fi
            }

            sudo_ready() {
              sudo -n true >/dev/null 2>&1
            }

            run_root() {
              local label="$1"
              shift
              if sudo_ready; then
                run_stream "$label" sudo -n "$@"
              else
                bullet "$label (requires sudo)"
                printf '    ↪ run manually: sudo %s\n' "$*"
              fi
            }

            printf '%sPerf scan mode:%s %s\n' "$bold" "$reset" "$MODE"
            echo "Log file: $log_file"
            echo "Scratch directory: $scratch"
            echo "Tip: close heavy applications (e.g. browsers, Spotify, games) before running full benchmarks for consistent numbers." | sed 's/^/  • /'

            section "System load"
            run_cmd "Timestamp" date
            run_cmd "Uptime & load" uptime
            run_stream "Top CPU consumers" sh -c 'ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 8'

            section "Hardware snapshot"
            run_stream "Kernel" uname -a
      run_stream "inxi -Fazy" inxi -Fazy --no-color
            run_stream "lscpu" lscpu
            run_stream "lsblk" lsblk -o NAME,MODEL,SIZE,ROTA,TYPE,MOUNTPOINT

            section "Thermals & power"
            run_if_exists "Sensors" sensors
            if have_cmd nvidia-smi; then
              run_stream "NVIDIA GPU summary" nvidia-smi --query-gpu=name,driver_version,pstate,clocks.gr,clocks.mem,temperature.gpu,power.draw --format=csv,noheader
            fi
            if sudo_ready; then
              powertop_csv="$scratch/powertop.csv"
              bullet "Powertop 10s snapshot -> $powertop_csv"
              set +e
              sudo -n powertop --time=10 --quiet --csv "$powertop_csv" >/dev/null 2>&1
              status=$?
              set -e
              if [[ $status -ne 0 ]]; then
                printf '    ↪ powertop capture failed (exit %d). Run manually: sudo powertop --html report.html\n' "$status"
              fi
            else
              bullet "Powertop snapshot (requires sudo)"
              printf '    ↪ run manually: sudo powertop --time=10 --csv report.csv\n'
            fi

            section "Storage health"
            for dev in /dev/nvme*n1; do
              [[ -e "$dev" ]] || continue
              run_root "NVMe SMART: $dev" nvme smart-log "$dev"
            done
            for dev in /dev/sd?; do
              [[ -e "$dev" ]] || continue
              run_root "SATA SMART: $dev" smartctl -H "$dev"
            done

            section "Quick benchmarks"
            run_stream "sysbench CPU (10k events)" sysbench cpu --max-requests=10000 --threads="$(nproc)"
      run_stream "sysbench memory (2GiB)" sysbench memory --threads="$(nproc)" --memory-total-size=2G --memory-block-size=4K run
            fio_file="$scratch/fio-seq.dat"
            run_stream "fio sequential read (512MiB)" fio --name=seqread --filename="$fio_file" --size=512M --bs=1M --rw=read --iodepth=32 --runtime=0 --time_based=0 --group_reporting
            phoronix-test-suite system-info 2>/dev/null | sed 's/^/    /' || true

            if [[ "$MODE" == "full" ]]; then
              section "Extended benchmarks"
              run_stream "stressapptest (3 min)" stressapptest -s 180 -W
              run_stream "fio random 4k read/write" fio --name=randrw --filename="$scratch/fio-rand.dat" --size=256M --bs=4k --rw=randrw --rwmixread=70 --iodepth=64 --runtime=60 --time_based --group_reporting
              if have_cmd glmark2; then
                run_stream "glmark2 (baseline)" glmark2 --run-forever off
              fi
              if have_cmd vkmark; then
                run_stream "vkmark (60s)" vkmark --duration 60
              fi
            fi

            section "Post-run load"
            run_cmd "Uptime & load" uptime
            run_stream "Top CPU consumers" sh -c 'ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 8'

            echo
            echo "Done. Review $log_file for full details."
    '';
  };
in
{
  config = {
    environment.systemPackages = [
      toggle_waybar
      perfScan
    ];
  };
}
