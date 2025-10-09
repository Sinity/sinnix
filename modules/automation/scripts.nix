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
      bc
      coreutils
      findutils
      gawk
      gnugrep
      gum
      hdparm
      intel-gpu-tools
      inxi
      iperf3
      iproute2
      jq
      ethtool
      flent
      lm_sensors
      memtester
      netperf
      nvme-cli
      pciutils
      perf
      linuxPackages.turbostat
      phoronix-test-suite
      powertop
      procps
      python3
      python312Packages.speedtest-cli
      rt-tests
      s-tui
      smartmontools
      stress-ng
      stressapptest
      sysbench
      sysstat
      util-linux
      vkmark
      glmark2
    ];
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      usage() {
        printf "%s\n" \
          "perf-scan - system diagnostics and benchmarking helper" \
          "" \
          "Usage: perf-scan [--full] [--log-dir DIR] [--network|--no-network]" \
          "                 [--gpu|--no-gpu] [--smart-long] [--power-calibrate]" \
          "                 [--json|--no-json]" \
          "" \
          "  --full              run extended (longer) benchmarks" \
          "  --log-dir DIR       write reports to DIR instead of $HOME/.cache/perf-scan" \
          "  --network           force-enable throughput/network stress tests" \
          "  --no-network        skip network throughput tests" \
          "  --gpu               force-enable GPU stress tests even in quick mode" \
          "  --no-gpu            skip GPU stress checks (both modes)" \
          "  --smart-long        trigger long SMART/NVMe self-tests (async, may take hours)" \
          "  --power-calibrate   run expensve powertop calibration first (requires sudo)" \
          "  --json / --no-json  toggle JSON summary export (default: on)" \
          "  --ui / --no-ui      force or disable the interactive menu" \
          "" \
          "Environment variables:" \
          "  PERF_SCAN_LOG_DIR       override the default report directory" \
          "  PERF_SCAN_MODE          same as --full when set to \"full\"" \
          "  PERF_SCAN_NETWORK       auto|enable|disable (default: auto)" \
          "  PERF_SCAN_GPU           auto|enable|disable (default: auto)" \
          "  PERF_SCAN_SMART_LONG    1 to start long SMART tests" \
          "  PERF_SCAN_POWER_CALIBRATE 1 to run powertop calibration" \
          "  PERF_SCAN_JSON          0 to disable JSON summary export" \
          "  PERF_SCAN_IPERF_HOST    host[:port] for iperf3" \
          "  PERF_SCAN_NETPERF_TEST  name of netperf test (default: TCP_STREAM)" \
          "" \
          "Most storage and power checks need passwordless sudo access. If sudo" \
          "credentials are required you will be prompted when the command runs."
      }

      MODE="''${PERF_SCAN_MODE:-quick}"
      LOG_DIR_OVERRIDE=""
      NETWORK_MODE="''${PERF_SCAN_NETWORK:-auto}"
      GPU_MODE="''${PERF_SCAN_GPU:-auto}"
      SMART_LONG=''${PERF_SCAN_SMART_LONG:-0}
      POWER_CALIBRATE=''${PERF_SCAN_POWER_CALIBRATE:-0}
      WANT_JSON=''${PERF_SCAN_JSON:-1}
      ui_mode="''${PERF_SCAN_UI:-auto}"
      cli_overrides=0

      while [[ $# -gt 0 ]]; do
        case "$1" in
          --full)
            MODE="full"
            cli_overrides=1
            shift
            ;;
          --log-dir)
            [[ $# -ge 2 ]] || { echo "--log-dir requires a path" >&2; exit 2; }
            LOG_DIR_OVERRIDE="$2"
            cli_overrides=1
            shift 2
            ;;
          --network)
            NETWORK_MODE="enable"
            cli_overrides=1
            shift
            ;;
          --no-network)
            NETWORK_MODE="disable"
            cli_overrides=1
            shift
            ;;
          --gpu)
            GPU_MODE="enable"
            cli_overrides=1
            shift
            ;;
          --no-gpu)
            GPU_MODE="disable"
            cli_overrides=1
            shift
            ;;
          --smart-long)
            SMART_LONG=1
            cli_overrides=1
            shift
            ;;
          --power-calibrate)
            POWER_CALIBRATE=1
            cli_overrides=1
            shift
            ;;
          --json)
            WANT_JSON=1
            cli_overrides=1
            shift
            ;;
          --no-json)
            WANT_JSON=0
            cli_overrides=1
            shift
            ;;
          --ui)
            ui_mode="on"
            shift
            ;;
          --no-ui)
            ui_mode="off"
            shift
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

      run_interactive() {
        gum style --border normal --margin "1 0" --padding "0 1" --bold "perf-scan interactive setup"

        local mode_choice
        if ! mode_choice=$(gum choose --header "Select the base run profile" \
            "Quick (~7 min) — smoke CPU/memory/disk" \
            "Full (~25 min) — extended stress & fio"); then
          echo "perf-scan cancelled." >&2
          exit 130
        fi

        case "$mode_choice" in
          Quick*) MODE="quick" ;;
          Full*) MODE="full" ;;
        esac

        local option_prompt="Toggle optional suites (space to select, enter when done)"
        local selections
        if ! selections=$(gum choose --no-limit --header "$option_prompt" \
            "Network jitter & throughput (~5 min, needs iperf host)" \
            "GPU stress (~3 min)" \
            "SMART long self-tests (async ≥1h, sudo)" \
            "Powertop calibration (~2 min, sudo)" \
            "Disable JSON summary"); then
          echo "perf-scan cancelled." >&2
          exit 130
        fi

        NETWORK_MODE="disable"
        GPU_MODE="disable"
        SMART_LONG=0
        POWER_CALIBRATE=0
        WANT_JSON=1

        if grep -q "Network jitter" <<< "$selections"; then
          NETWORK_MODE="enable"
        fi
        if grep -q "GPU stress" <<< "$selections"; then
          GPU_MODE="enable"
        fi
        if grep -q "SMART long" <<< "$selections"; then
          SMART_LONG=1
        fi
        if grep -q "Powertop calibration" <<< "$selections"; then
          POWER_CALIBRATE=1
        fi
        if grep -q "Disable JSON" <<< "$selections"; then
          WANT_JSON=0
        fi

        if [[ $NETWORK_MODE == "enable" ]]; then
          local host_value
          host_value=''${PERF_SCAN_IPERF_HOST:-}
          if [[ -z "$host_value" ]]; then
            host_value=$(gum input --header "iperf3 host[:port] for network tests" --placeholder "example.com:5201" || true)
          fi
          if [[ -n "$host_value" ]]; then
            export PERF_SCAN_IPERF_HOST="$host_value"
          else
            NETWORK_MODE="disable"
          fi
        fi

        local est_minutes
        if [[ $MODE == "full" ]]; then
          est_minutes=25
        else
          est_minutes=7
        fi
        [[ $NETWORK_MODE == "enable" ]] && est_minutes=$((est_minutes + 5))
        [[ $GPU_MODE == "enable" ]] && est_minutes=$((est_minutes + 3))
        [[ $POWER_CALIBRATE -eq 1 ]] && est_minutes=$((est_minutes + 2))

        local mode_label
        mode_label=''${MODE^^}
        local network_label="disabled"
        [[ $NETWORK_MODE == "enable" ]] && network_label="enabled"
        local gpu_label="disabled"
        [[ $GPU_MODE == "enable" ]] && gpu_label="enabled"
        local powertop_label="disabled"
        [[ $POWER_CALIBRATE -eq 1 ]] && powertop_label="enabled"
        local json_label="enabled"
        [[ $WANT_JSON -eq 0 ]] && json_label="disabled"

        local estimate_line="Estimated runtime ≈ ''${est_minutes} minutes"
        if [[ $SMART_LONG -eq 1 ]]; then
          estimate_line+=" (+ async SMART long tests)"
        fi

        gum style --padding "0 1" \
          "Mode: $mode_label" \
          "Network: $network_label" \
          "GPU stress: $gpu_label" \
          "Powertop calibration: $powertop_label" \
          "JSON summary: $json_label"
        gum style --margin "0 0 1 0" --faint "$estimate_line"
      }

                  if [[ $ui_mode != "off" && -z "''${PERF_SCAN_NO_UI:-}" && $cli_overrides -eq 0 ]]; then
                    if command -v gum >/dev/null 2>&1; then
                      run_interactive
                    elif [[ $ui_mode == "on" ]]; then
                      echo "gum not available; running in non-interactive mode." >&2
                    fi
                  fi

                  LOG_ROOT="''${LOG_DIR_OVERRIDE:-''${PERF_SCAN_LOG_DIR:-$HOME/.cache/perf-scan}}"
                  mkdir -p "$LOG_ROOT"
                  timestamp=$(date +'%Y%m%d-%H%M%S')
                  log_file="$LOG_ROOT/perf-scan-''${MODE}-''${timestamp}.log"
                  json_file="$LOG_ROOT/perf-scan-''${MODE}-''${timestamp}.json"

                  scratch=$(mktemp -d "''${TMPDIR:-/tmp}/perf-scan.XXXXXX")
                  total_start=$(date +%s)
                  cleanup() {
                    local total_end elapsed
                    total_end=$(date +%s)
                    elapsed=$((total_end - total_start))
                    printf '\nReports saved to: %s\n' "$log_file"
                    if [[ $WANT_JSON -eq 1 ]]; then
                      printf 'JSON summary: %s\n' "$json_file"
                    fi
                    printf 'Scratch data kept in: %s\n' "$scratch"
                    printf 'Total elapsed: %s\n' "$(format_duration "$elapsed")"
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
        if command -v gum >/dev/null 2>&1; then
          printf "\n"
          gum style --border normal --bold --padding "0 1" --margin "1 0 0 0" --align center "$1" \
            || printf "\n%s== %s ==%s\n" "$bold" "$1" "$reset"
        else
          printf "\n%s== %s ==%s\n" "$bold" "$1" "$reset"
        fi
      }

            bullet() {
              printf "  • %s\n" "$1"
            }

                  format_duration() {
                    local total="$1"
                    if [[ -z "$total" || "$total" -le 0 ]]; then
                      printf '0s'
                      return
                    fi
                    local h=$((total / 3600))
                    local m=$(((total % 3600) / 60))
                    local s=$((total % 60))
                    if ((h > 0)); then
                      printf '%dh%02dm%02ds' "$h" "$m" "$s"
                    elif ((m > 0)); then
                      printf '%dm%02ds' "$m" "$s"
                    else
                      printf '%ds' "$s"
                    fi
                  }

                  json_escape() {
                    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
                  }

      summary=()
      summary_json=()

                  add_summary() {
                    local kind="$1"
                    local label="$2"
                    local duration="''${3:-}"
                    local note="''${4:-}"
                    case "$kind" in
                      ok)
                        if [[ -n "$duration" ]]; then
                          summary+=("✓ $label ($duration)")
                        else
                          summary+=("✓ $label")
                        fi
                        ;;
                      fail)
                        if [[ -n "$duration" ]]; then
                          summary+=("✗ $label ($duration)")
                        else
                          summary+=("✗ $label")
                        fi
                        ;;
                      skip)
                        if [[ -n "$duration" ]]; then
                          summary+=("– $label ($duration)")
                        else
                          summary+=("– $label")
                        fi
                        ;;
                    esac
                    if [[ $WANT_JSON -eq 1 ]]; then
                      local escaped_label
                      escaped_label=$(json_escape "$label")
                      local obj="{\"status\":\"''${kind}\",\"label\":\"''${escaped_label}\""
                      if [[ -n "$duration" ]]; then
                        local escaped_duration
                        escaped_duration=$(json_escape "$duration")
                        obj+="\",\"duration\":\"''${escaped_duration}\""
                      fi
                      if [[ -n "$note" ]]; then
                        local escaped_note
                        escaped_note=$(json_escape "$note")
                        obj+="\",\"note\":\"''${escaped_note}\""
                      fi
                      obj+='}'
                      summary_json+=("$obj")
                    fi
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
                    return $status
                  }

                  run_stream() {
                    local label="$1"
                    shift
                    bullet "$label"
                    set +e
                    set -o pipefail
                    "$@" 2>&1 | sed 's/^/    /'
                    local status=$?
                    set +o pipefail
                    set -e
                    if [[ $status -ne 0 ]]; then
                      printf '    ↪ command exited with %d\n' "$status"
                    fi
                    return $status
                  }

                  track_stream() {
                    local label="$1"
                    shift
                    local start_ts
                    start_ts=$(date +%s)
                    if run_stream "$label" "$@"; then
                      local end_ts
                      end_ts=$(date +%s)
                      add_summary ok "$label" "$(format_duration $((end_ts - start_ts)))"
                    else
                      local status=$?
                      local end_ts
                      end_ts=$(date +%s)
                      add_summary fail "$label (exit $status)" "$(format_duration $((end_ts - start_ts)))"
                    fi
                    return 0
                  }

                  have_cmd() {
                    command -v "$1" >/dev/null 2>&1
                  }

                  run_if_exists() {
                    local label="$1"
                    shift
                    local cmd="$1"
                    if have_cmd "$cmd"; then
                      track_stream "$label" "$@"
                    else
                      local message="$label (tool not available: $cmd)"
                      bullet "$message"
                      add_summary skip "$message" "" "missing tool"
                    fi
                  }

                  sudo_ready() {
                    sudo -n true >/dev/null 2>&1
                  }

                  run_root() {
                    local label="$1"
                    shift
                if sudo_ready; then
                  local start_ts
                  start_ts=$(date +%s)
                  if run_stream "$label" sudo -n "$@"; then
                    local end_ts
                    end_ts=$(date +%s)
                    add_summary ok "$label" "$(format_duration $((end_ts - start_ts)))"
                  else
                    local status=$?
                    local end_ts
                    end_ts=$(date +%s)
                    add_summary fail "$label (exit $status)" "$(format_duration $((end_ts - start_ts)))"
                  fi
                    else
                      bullet "$label (requires sudo)"
                      printf '    ↪ run manually: sudo %s\n' "$*"
                      add_summary skip "$label (sudo required)" "" "sudo unavailable"
                    fi
                  }

                  smart_short_test() {
                    local dev="$1"
                    bullet "SMART short self-test: $dev"
                    if ! sudo_ready; then
                      printf '    ↪ run manually: sudo smartctl -t short %s\n' "$dev"
                      add_summary skip "SMART short self-test $dev" "" "sudo required"
                      return
                    fi
                local start_ts
                start_ts=$(date +%s)
                    set +e
                    local kickoff
                    kickoff=$(sudo -n smartctl -t short "$dev" 2>&1)
                    local kickoff_status=$?
                    set -e
                    if [[ -n "$kickoff" ]]; then
                      printf '%s\n' "$kickoff" | sed 's/^/    /'
                    fi
                    if [[ $kickoff_status -ne 0 ]]; then
                      add_summary fail "SMART short self-test $dev (start)" "" "exit $kickoff_status"
                      return
                    fi
                local wait_secs
                    wait_secs=$(echo "$kickoff" | awk '/[Pp]lease wait|complete/ { for (i=1; i<=NF; i++) if ($i ~ /^[0-9]+$/) { print $i; exit } }')
                    if [[ -z "$wait_secs" || ! "$wait_secs" =~ ^[0-9]+$ ]]; then
                      wait_secs=120
                    fi
                    if ((wait_secs > 600)); then
                      wait_secs=600
                    fi
                    printf '    ↪ waiting %s for completion...\n' "$(format_duration "$wait_secs")"
                    sleep "$wait_secs"
                    set +e
                local result
                    result=$(sudo -n smartctl -l selftest "$dev" 2>&1)
                    local result_status=$?
                    set -e
                    if [[ -n "$result" ]]; then
                      printf '%s\n' "$result" | sed 's/^/    /'
                    fi
                local end_ts
                end_ts=$(date +%s)
                    if [[ $result_status -eq 0 ]]; then
                      add_summary ok "SMART short self-test $dev" "$(format_duration $((end_ts - start_ts)))"
                    else
                      add_summary fail "SMART short self-test $dev (log exit $result_status)" "$(format_duration $((end_ts - start_ts)))"
                    fi
                  }

                  trigger_smart_long() {
                    local dev="$1"
                    bullet "SMART long self-test: $dev (async)"
                    if ! sudo_ready; then
                      printf '    ↪ run manually: sudo smartctl -t long %s\n' "$dev"
                      add_summary skip "SMART long self-test $dev" "" "sudo required"
                      return
                    fi
                    set +e
                    local kickoff
                    kickoff=$(sudo -n smartctl -t long "$dev" 2>&1)
                    local kickoff_status=$?
                    set -e
                    if [[ -n "$kickoff" ]]; then
                      printf '%s\n' "$kickoff" | sed 's/^/    /'
                    fi
                    if [[ $kickoff_status -eq 0 ]]; then
                      add_summary ok "SMART long self-test started $dev" "" "check later via smartctl -l selftest"
                    else
                      add_summary fail "SMART long self-test $dev" "" "start exit $kickoff_status"
                    fi
                  }

                  trigger_nvme_long() {
                    local dev="$1"
                    bullet "NVMe extended self-test: $dev (async)"
                    if ! sudo_ready; then
                      printf '    ↪ run manually: sudo nvme device-self-test %s --st 2\n' "$dev"
                      add_summary skip "NVMe long self-test $dev" "" "sudo required"
                      return
                    fi
                    set +e
                    local kickoff
                    kickoff=$(sudo -n nvme device-self-test "$dev" --st 2 2>&1)
                    local kickoff_status=$?
                    set -e
                    if [[ -n "$kickoff" ]]; then
                      printf '%s\n' "$kickoff" | sed 's/^/    /'
                    fi
                    if [[ $kickoff_status -eq 0 ]]; then
                      add_summary ok "NVMe long self-test started $dev" "" "check later via nvme device-self-test -r"
                    else
                      add_summary fail "NVMe long self-test $dev" "" "start exit $kickoff_status"
                    fi
                  }

                  maybe_network=
                  if [[ "$NETWORK_MODE" == "enable" ]]; then
                    maybe_network=1
                  elif [[ "$NETWORK_MODE" == "disable" ]]; then
                    maybe_network=0
                  elif [[ "$MODE" == "full" ]]; then
                    maybe_network=1
                  else
                    maybe_network=0
                  fi

                  maybe_gpu=
                  if [[ "$GPU_MODE" == "enable" ]]; then
                    maybe_gpu=1
                  elif [[ "$GPU_MODE" == "disable" ]]; then
                    maybe_gpu=0
                  elif [[ "$MODE" == "full" ]]; then
                    maybe_gpu=1
                  else
                    maybe_gpu=0
                  fi

                  printf '%sPerf scan mode:%s %s\n' "$bold" "$reset" "$MODE"
                  echo "Log file: $log_file"
                  echo "Scratch directory: $scratch"
                  echo "Tip: close heavy applications (e.g. browsers, Spotify, games) before running full benchmarks for consistent numbers." | sed 's/^/  • /'
                  if [[ $maybe_network -eq 1 ]]; then
                    echo "  • Network throughput tests will run; ensure no bandwidth caps are in place." 
                  fi
                  if [[ $SMART_LONG -eq 1 ]]; then
                    echo "  • Long SMART/NVMe tests can take 1-2 hours; results must be checked manually afterwards." | sed 's/^/  • /'
                  fi

                  section "System load"
                  run_cmd "Timestamp" date
                  run_cmd "Uptime & load" uptime
                  track_stream "Top CPU consumers" sh -c 'ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 8'
                  track_stream "Top memory consumers" sh -c 'ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 8'

                  section "Hardware snapshot"
                  track_stream "Kernel" uname -a
                  track_stream "inxi -Fazy" inxi -Fazy --color 0
                  track_stream "lscpu" lscpu
                  track_stream "lsblk" lsblk -o NAME,MODEL,SIZE,ROTA,TYPE,MOUNTPOINT
                  run_if_exists "lspci" lspci -nn

                  section "Network snapshot"
                  run_if_exists "ip -brief address" ip -brief address
                  run_if_exists "ss -s" ss -s
                  if have_cmd ethtool; then
                    for nic_path in /sys/class/net/*; do
                      nic="''${nic_path##*/}"
                      [[ "$nic" == "lo" ]] && continue
                      run_if_exists "ethtool $nic" ethtool "$nic"
                      if have_cmd ethtool; then
                        ethtool -S "$nic" >"$scratch/ethtool-$nic.txt" 2>/dev/null && bullet "Saved ethtool stats for $nic -> $scratch/ethtool-$nic.txt"
                      fi
                    done
                  fi

                  if have_cmd iw; then
                    run_if_exists "Wi-Fi info" iw dev
                  fi

                  section "Thermals & power"
                  run_if_exists "Sensors" sensors
                  if have_cmd nvidia-smi; then
                    track_stream "NVIDIA GPU summary" nvidia-smi --query-gpu=name,driver_version,pstate,clocks.gr,clocks.mem,temperature.gpu,power.draw --format=csv,noheader
                  fi
                  if have_cmd intel_gpu_top; then
                    if command -v timeout >/dev/null 2>&1; then
                      timeout 15 intel_gpu_top -J -s 200 >"$scratch/intel_gpu_top.json" 2>/dev/null || true
                      bullet "intel_gpu_top JSON capture -> $scratch/intel_gpu_top.json"
                    fi
                  fi
                  if have_cmd s-tui; then
                    track_stream "s-tui snapshot (non-interactive)" timeout 60 s-tui -c || true
                  fi
                  if [[ $POWER_CALIBRATE -eq 1 ]]; then
                    run_root "Powertop calibration" powertop --calibrate
                  fi
              if sudo_ready; then
                powertop_csv="$scratch/powertop.csv"
                bullet "Powertop 10s snapshot -> $powertop_csv"
                powertop_start_ts=$(date +%s)
                set +e
                    sudo -n powertop --time=10 --quiet --csv "$powertop_csv" >/dev/null 2>&1
                    powertop_status=$?
                    set -e
                    powertop_end_ts=$(date +%s)
                    if [[ $powertop_status -ne 0 ]]; then
                      printf '    ↪ powertop capture failed (exit %d). Run manually: sudo powertop --html report.html\n' "$powertop_status"
                      add_summary fail "Powertop snapshot (exit $powertop_status)" "$(format_duration $((powertop_end_ts - powertop_start_ts)))"
                    else
                      add_summary ok "Powertop snapshot ($powertop_csv)" "$(format_duration $((powertop_end_ts - powertop_start_ts)))"
                    fi
                  else
                    bullet "Powertop snapshot (requires sudo)"
                    printf '    ↪ run manually: sudo powertop --time=10 --csv report.csv\n'
                add_summary skip "Powertop snapshot (sudo required)" "" "sudo unavailable"
              fi

              section "Scheduler telemetry"
              run_if_exists "perf stat (15s all CPUs)" perf stat --all-cpus --interval-print 5 -- sleep 15
              if have_cmd turbostat; then
                run_root "turbostat (20s sample)" turbostat --Summary --interval 5 --num_iterations 4
              else
                bullet "turbostat sample (tool not available: turbostat)"
                add_summary skip "turbostat sample" "" "missing turbostat"
              fi

              section "Storage health"
              for dev in /dev/nvme*n1; do
                [[ -e "$dev" ]] || continue
                run_root "NVMe SMART: $dev" nvme smart-log "$dev"
                    run_root "NVMe error-log: $dev" nvme error-log "$dev"
                    run_root "NVMe firmware-log: $dev" nvme fw-log "$dev"
                    if [[ "$MODE" == "full" ]]; then
                      run_root "NVMe SMART extended: $dev" nvme smart-log-add "$dev"
                      if [[ $SMART_LONG -eq 1 ]]; then
                        trigger_nvme_long "$dev"
                      fi
                    fi
                  done
                  for dev in /dev/sd?; do
                    [[ -e "$dev" ]] || continue
                    if [[ "$MODE" == "full" ]]; then
                      run_root "SATA SMART detail: $dev" smartctl -a "$dev"
                    else
                      run_root "SATA SMART: $dev" smartctl -H "$dev"
                    fi
                    if [[ $SMART_LONG -eq 1 ]]; then
                      trigger_smart_long "$dev"
                    fi
                  done

                  section "Quick benchmarks"
                  track_stream "sysbench CPU (10k events)" sysbench cpu --max-requests=10000 --threads="$(nproc)"
                  track_stream "sysbench memory (2GiB)" sysbench memory --threads="$(nproc)" --memory-total-size=2G --memory-block-size=4K run
                  fio_file="$scratch/fio-seq.dat"
                  track_stream "fio sequential read (512MiB)" fio --name=seqread --filename="$fio_file" --size=512M --bs=1M --rw=read --iodepth=32 --runtime=0 --time_based=0 --group_reporting
                  rm -f "$fio_file"
                  run_if_exists "Phoronix system-info" phoronix-test-suite system-info

                  if [[ $maybe_network -eq 1 ]]; then
                    section "Network throughput"
                    if have_cmd speedtest-cli; then
                      track_stream "Speedtest.net (Ookla CLI)" speedtest-cli --secure --timeout 30
                    else
                      bullet "Speedtest (requires speedtest-cli)"
                      add_summary skip "Speedtest" "" "speedtest-cli missing"
                    fi
                    if [[ -n "''${PERF_SCAN_IPERF_HOST-}" ]]; then
                perf_scan_host="''${PERF_SCAN_IPERF_HOST%%:*}"

                      if have_cmd iperf3; then
                        track_stream "iperf3 down" iperf3 -R -c "$PERF_SCAN_IPERF_HOST" -t 15
                        track_stream "iperf3 up" iperf3 -c "$PERF_SCAN_IPERF_HOST" -t 15
                        track_stream "iperf3 UDP jitter down" iperf3 -u -b 0 -R -c "$PERF_SCAN_IPERF_HOST" -t 10
                        track_stream "iperf3 UDP jitter up" iperf3 -u -b 0 -c "$PERF_SCAN_IPERF_HOST" -t 10
                      else
                        bullet "iperf3 tests skipped (iperf3 missing)"
                        add_summary skip "iperf3 tests" "" "iperf3 missing"
                      fi

                if have_cmd netperf; then
                  netperf_test=$PERF_SCAN_NETPERF_TEST
                  if [[ -z $netperf_test ]]; then
                    netperf_test=TCP_STREAM
                  fi
                  track_stream "netperf $netperf_test" netperf -H "$perf_scan_host" "$netperf_test" -l 20
                else
                  bullet "netperf test skipped (netperf missing)"
                  add_summary skip "netperf" "" "netperf missing"
                fi

                if have_cmd flent; then
                  flent_output="$scratch/flent-rrul.flent.gz"
                  track_stream "flent rrul (20s)" flent rrul -H "$perf_scan_host" -l 20 --log-file "$flent_output"
                  if [[ -f "$flent_output" ]]; then
                    bullet "flent log saved -> $flent_output"
                  fi
                else
                  bullet "flent rrul skipped (flent missing)"
                  add_summary skip "flent rrul" "" "flent missing"
                fi
                    else
                      bullet "iperf3/netperf tests skipped (set PERF_SCAN_IPERF_HOST to enable)"
                      add_summary skip "iperf3/netperf" "" "PERF_SCAN_IPERF_HOST not set"
                    fi
                  fi

                  if [[ "$MODE" == "full" ]]; then
                    section "Extended CPU & memory stress"
                    track_stream "stressapptest (10 min)" stressapptest -s 600 -W
                    run_if_exists "stress-ng cpu matrix (4 min)" stress-ng --cpu "$(nproc)" --cpu-method matrixprod --timeout 240s --metrics-brief
                    run_if_exists "stress-ng cpu all-methods (2 min)" stress-ng --cpu "$(nproc)" --cpu-method all --timeout 120s --metrics-brief
                    run_if_exists "stress-ng vm (70% RAM, 3 min)" stress-ng --vm "$(( ( $(nproc) + 1 ) / 2 ))" --vm-bytes 70% --timeout 180s --metrics-brief
              if have_cmd memtester; then
                mem_avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
                memtester_size_mb=$((mem_avail_kb * 60 / 100 / 1024))
                      if ((memtester_size_mb < 128)); then
                        memtester_size_mb=128
                      fi
                      track_stream "memtester (''${memtester_size_mb}M x1)" memtester "''${memtester_size_mb}M" 1
                    else
                      bullet "memtester not available"
                      add_summary skip "memtester" "" "memtester missing"
                    fi
                    run_if_exists "Intel MLC bandwidth" mlc --bandwidth_matrix
                    run_if_exists "Intel MLC latency" mlc --latency_matrix
                    run_if_exists "perf bench sched pipe" perf bench sched pipe
                    run_root "cyclictest (120s)" cyclictest --duration=120s --priority=95 --interval=1000 --quiet
                    run_if_exists "latencytop sample" latencytop -n -d 5 || true

                    section "Extended storage benchmarks"
                    fio_seq_ext="$scratch/fio-seq-extended.dat"
                    track_stream "fio sequential write (2GiB, direct)" fio --name=seqwrite --filename="$fio_seq_ext" --size=2G --bs=1M --rw=write --direct=1 --iodepth=64 --group_reporting
                    track_stream "fio sequential read (2GiB, direct)" fio --name=seqread --filename="$fio_seq_ext" --size=2G --bs=1M --rw=read --direct=1 --iodepth=64 --group_reporting
                    rm -f "$fio_seq_ext"
                    fio_rand_ext="$scratch/fio-rand-extended.dat"
                    track_stream "fio random mixed 4k (70% read, 5 min)" fio --name=randmix --filename="$fio_rand_ext" --size=2G --bs=4k --rw=randrw --rwmixread=70 --iodepth=128 --runtime=300 --time_based --group_reporting
                    track_stream "fio random read QD32 (3 min)" fio --name=randread --filename="$fio_rand_ext" --size=1G --bs=4k --rw=randread --iodepth=32 --runtime=180 --time_based --group_reporting
                    rm -f "$fio_rand_ext"

                    section "SMART self-tests"
                    for dev in /dev/sd?; do
                      [[ -e "$dev" ]] || continue
                      smart_short_test "$dev"
                    done

                    section "Observability captures"
                    track_stream "iostat extended (5s x3)" iostat -xz 5 3

                    if [[ $maybe_gpu -eq 1 ]]; then
                section "GPU stress"
                run_if_exists "glmark2 (baseline)" glmark2 --run-forever off
                run_if_exists "vkmark (60s)" vkmark --duration 60
                if have_cmd nvidia-smi; then
                  track_stream "nvidia-smi pmon (10 samples)" timeout 10 nvidia-smi pmon -s um
                  track_stream "nvidia-smi dmon (60s)" timeout 60 nvidia-smi dmon -s pucvmet
                fi
              fi
            elif [[ $maybe_gpu -eq 1 ]]; then
              section "GPU stress"
              run_if_exists "glmark2 (baseline)" glmark2 --run-forever off
              run_if_exists "vkmark (60s)" vkmark --duration 60
              if have_cmd nvidia-smi; then
                track_stream "nvidia-smi pmon (10 samples)" timeout 10 nvidia-smi pmon -s um
              fi
            fi

                  section "Post-run load"
                  run_cmd "Uptime & load" uptime
                  track_stream "Top CPU consumers" sh -c 'ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 8'
                  track_stream "Top memory consumers" sh -c 'ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 8'

                  section "Summary"
                  if ((''${#summary[@]})); then
                    for entry in "''${summary[@]}"; do
                      printf '  %s\n' "$entry"
                    done
                  else
                    echo "  • No benchmarked items recorded."
                  fi

                  if [[ $WANT_JSON -eq 1 ]]; then
                    if ((''${#summary_json[@]})); then
                      printf '[\n%s\n]\n' "$(printf '%s\n' "''${summary_json[@]}" | sed 's/^/  /' | paste -sd ',\n' -)" >"$json_file"
                    else
                      printf '[]\n' >"$json_file"
                    fi
                  fi

                  echo
                  echo "Done. Review $log_file for full details."
    '';
  };

  kittyGrid = pkgs.writeShellApplication {
    name = "kitty-image-grid";
    runtimeInputs = with pkgs; [
      coreutils
      findutils
      file
      kitty
      python3
    ];
    text = builtins.readFile ../../module/asset/kitty-image-grid.sh;
  };

  visionModelsSync = pkgs.writeShellApplication {
    name = "sync-vision-models";
    runtimeInputs = with pkgs; [
      bash
      coreutils
      curl
      openssl
    ];
    text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            MODEL_ROOT="''${MODEL_ROOT:-/realm/data/model}"
            mkdir -p "$MODEL_ROOT"

            manifest=$(cat <<'EOF'
      wd-convnextv2|taggers|https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2/resolve/main/model.onnx?download=1|model.onnx|f8a067d17cf739219d9aa61bde2cdfcf744f0f77c00e0c8d16516e7620c37756
      wd-moat|taggers|https://huggingface.co/SmilingWolf/wd-v1-4-moat-tagger-v2/resolve/main/model.onnx?download=1|model.onnx|9a6f78ed76c0681903e9267b2f4deab559bc6f5d1c11d0e99cb4f602d00cbbff
      siglip-so400m|embeddings|https://huggingface.co/google/siglip-so400m-patch14-384/resolve/main/model.fp16.onnx?download=1|model.fp16.onnx|05b1df0d79ae9a44cc979f409775888b859504a829148d464472b725f0c602ca
      clip-bigG|embeddings|https://huggingface.co/laion/CLIP-ViT-bigG-14-laion2B-39B-b160k/resolve/main/open_clip_pytorch_model.bin?download=1|open_clip_pytorch_model.bin|6e5ddd339a95df833295673eee1268db15bf95df2da233c6f0ca6c584108a52d
      photoprism-face-rec|photoprism|https://dl.photoprism.app/tensorflow/facenet.pb.zip|facenet.pb.zip|a24a967c3db01a0c7b10bce7d712aa41d167c94656094c69a517bd7be3c7eca5
      EOF
            )

            download() {
              local name="$1"; shift
              local subdir="$1"; shift
              local url="$1"; shift
              local filename="$1"; shift
              local sha256_expected="$1"; shift

              local target_dir="$MODEL_ROOT/$subdir/$name"
              local target_path="$target_dir/$filename"
              local tmp_path="$target_path.part"

              mkdir -p "$target_dir"

              if [[ -f "$target_path" ]]; then
                if [[ -n "$sha256_expected" ]]; then
                  checksum=$(openssl dgst -sha256 "$target_path" | awk '{print $2}')
                  if [[ "$checksum" == "$sha256_expected" ]]; then
                    printf '✓ %s already present (verified)\n' "$name"
                    return
                  fi
                fi
                mv "$target_path" "$target_path.bak"
              fi

              printf '→ downloading %s\n' "$name"
              curl --fail --location --continue-at - --output "$tmp_path" "$url"

              if [[ -n "$sha256_expected" ]]; then
                checksum=$(openssl dgst -sha256 "$tmp_path" | awk '{print $2}')
                if [[ "$checksum" != "$sha256_expected" ]]; then
                  printf '✗ checksum mismatch for %s (expected %s, got %s)\n' "$name" "$sha256_expected" "$checksum" >&2
                  return 1
                fi
              fi

              mv "$tmp_path" "$target_path"
              printf '✓ stored %s → %s\n' "$name" "$target_path"
            }

            while IFS='|' read -r name subdir url filename sha; do
              [[ -n "$name" ]] || continue
              download "$name" "$subdir" "$url" "$filename" "$sha"
            done <<< "$manifest"
    '';
  };
in
{
  environment.systemPackages = [
    toggle_waybar
    perfScan
    kittyGrid
    visionModelsSync
  ];
}
