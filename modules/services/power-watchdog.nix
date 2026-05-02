# power-watchdog: High-frequency sensor logger for power loss forensics
#
# Logs CPU/GPU/NVMe temperatures, GPU power/link state, and system load every second
# to a persistent CSV file with periodic file-data sync.
#
# Purpose: When the system power-cycles unexpectedly, this gives us the last
# known sensor state to correlate with the crash. Unlike `below` which captures
# CPU/memory scheduling, this captures thermal and power telemetry.
#
# Design: Reads sysfs hwmon files directly (no process spawning for temps) to
# achieve 1-second resolution. Only nvidia-smi requires a subprocess (~54ms).
# Hwmon indices are discovered dynamically at startup by matching chip names.
#
# Data stored in: ${capturesRoot}/power-watchdog/
# Format: CSV with millisecond timestamps, one row per sample
# Retention: configurable, defaults to 30 days
# Storage: sample data is small. Flush with file-data sync only; filesystem-wide
# sync turns telemetry writes into unrelated Btrfs/git/Sinex writeback stalls.
#
# Query examples:
#   # Last 100 samples before a crash (check timestamps):
#   tail -100 /realm/data/captures/power-watchdog/sensors.csv
#
#   # Plot GPU power draw over time:
#   awk -F, '{print $1, $14}' sensors.csv
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  ...
}@args:
let
  inherit (config.sinnix.paths) capturesRoot;
  dataDir = "${capturesRoot}/power-watchdog";
  username = config.sinnix.user.name;

  powerWatchdog = pkgs.writeShellApplication {
    name = "power-watchdog";
    runtimeInputs = with pkgs; [
      coreutils
      gawk
    ];
    text = ''
      set -euo pipefail

      INTERVAL="''${1:-1}"
      DATA_DIR="${dataDir}"
      CSV_FILE="$DATA_DIR/sensors.csv"
      RETENTION_DAYS="''${2:-30}"
      FLUSH_EVERY_SAMPLES="''${3:-15}"

      mkdir -p "$DATA_DIR"

      # === Dynamic hwmon discovery ===
      # hwmon indices can change across reboots, so discover by chip name
      find_hwmon() {
        local target_name="$1"
        local occurrence="''${2:-1}"
        local count=0
        for hwmon in /sys/class/hwmon/hwmon*; do
          if [ -f "$hwmon/name" ] && [ "$(cat "$hwmon/name")" = "$target_name" ]; then
            count=$((count + 1))
            if [ "$count" -eq "$occurrence" ]; then
              echo "$hwmon"
              return
            fi
          fi
        done
        echo ""
      }

      CORETEMP=$(find_hwmon "coretemp")
      GWMI=$(find_hwmon "gigabyte_wmi")
      SPD1=$(find_hwmon "spd5118" 1)
      SPD2=$(find_hwmon "spd5118" 2)
      NVME1=$(find_hwmon "nvme" 1)
      NVME2=$(find_hwmon "nvme" 2)

      # Validate critical paths exist
      if [ -z "$CORETEMP" ]; then
        echo "FATAL: coretemp hwmon not found" >&2
        exit 1
      fi

      echo "power-watchdog: discovered hwmon paths:" >&2
      echo "  coretemp=$CORETEMP gwmi=$GWMI" >&2
      echo "  spd5118=$SPD1,$SPD2 nvme=$NVME1,$NVME2" >&2
      echo "  interval=''${INTERVAL}s retention=''${RETENTION_DAYS}d flush_every=''${FLUSH_EVERY_SAMPLES} samples" >&2

      # Best-effort flush on service stop/crash.
      trap 'sync -d "$CSV_FILE" 2>/dev/null || true' EXIT

      # === Helper: read sysfs temp (millidegrees → degrees with 1 decimal) ===
      read_temp() {
        local val
        val=$(cat "$1" 2>/dev/null || true)
        if [ -n "$val" ]; then
          awk "BEGIN{printf \"%.1f\", $val/1000}"
        else
          echo "0"
        fi
      }

      # === Helper: max of all coretemp sensors ===
      read_max_coretemp() {
        local max=0
        for f in "$CORETEMP"/temp*_input; do
          val=$(cat "$f" 2>/dev/null) || continue
          if [ "$val" -gt "$max" ] 2>/dev/null; then
            max=$val
          fi
        done
        awk "BEGIN{printf \"%.1f\", $max/1000}"
      }

      # Write CSV header if file doesn't exist or is empty
      if [ ! -s "$CSV_FILE" ]; then
        echo "timestamp,cpu_pkg_c,cpu_max_core_c,ddr5_1_c,ddr5_2_c,nvme_1_c,nvme_2_c,gwmi_1_c,gwmi_2_c,gwmi_3_c,gwmi_4_c,gwmi_5_c,gwmi_6_c,gpu_temp_c,gpu_power_w,gpu_power_limit_w,gpu_fan_pct,gpu_util_pct,gpu_mem_util_pct,gpu_clk_mhz,gpu_mem_clk_mhz,gpu_pstate,gpu_pcie_gen,gpu_pcie_width,load_1m,load_5m,mem_used_mb,mem_avail_mb,swap_used_mb" > "$CSV_FILE"
      fi

      # Rotation: once per day, trim lines older than retention
      last_rotate=$(date +%s)
      rotate_if_needed() {
        local now
        now=$(date +%s)
        if (( now - last_rotate > 86400 )); then
          local cutoff
          cutoff=$(date -d "-$RETENTION_DAYS days" +%Y-%m-%dT%H:%M:%S 2>/dev/null || echo "")
          if [ -n "$cutoff" ] && [ -f "$CSV_FILE" ]; then
            local tmp="$CSV_FILE.tmp"
            head -1 "$CSV_FILE" > "$tmp"
            awk -F, -v cutoff="$cutoff" 'NR>1 && $1 >= cutoff' "$CSV_FILE" >> "$tmp"
            mv "$tmp" "$CSV_FILE"
          fi
          last_rotate=$now
        fi
      }

      # === Main loop ===
      samples_since_flush=0
      while true; do
        ts=$(date +%Y-%m-%dT%H:%M:%S.%3N)

        # --- Direct sysfs reads (no process spawning, ~2ms total) ---
        cpu_pkg=$(read_temp "$CORETEMP/temp1_input")
        cpu_max=$(read_max_coretemp)

        ddr5_1=0; ddr5_2=0
        [ -n "$SPD1" ] && ddr5_1=$(read_temp "$SPD1/temp1_input")
        [ -n "$SPD2" ] && ddr5_2=$(read_temp "$SPD2/temp1_input")

        nvme_1=0; nvme_2=0
        [ -n "$NVME1" ] && nvme_1=$(read_temp "$NVME1/temp1_input")
        [ -n "$NVME2" ] && nvme_2=$(read_temp "$NVME2/temp1_input")

        gwmi_1=0; gwmi_2=0; gwmi_3=0; gwmi_4=0; gwmi_5=0; gwmi_6=0
        if [ -n "$GWMI" ]; then
          gwmi_1=$(read_temp "$GWMI/temp1_input")
          gwmi_2=$(read_temp "$GWMI/temp2_input")
          gwmi_3=$(read_temp "$GWMI/temp3_input")
          gwmi_4=$(read_temp "$GWMI/temp4_input")
          gwmi_5=$(read_temp "$GWMI/temp5_input")
          gwmi_6=$(read_temp "$GWMI/temp6_input")
        fi

        # --- GPU data (nvidia-smi, ~54ms) ---
        gpu_line=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,power.limit,fan.speed,utilization.gpu,utilization.memory,clocks.current.graphics,clocks.current.memory,pstate,pcie.link.gen.gpucurrent,pcie.link.width.current --format=csv,noheader,nounits 2>/dev/null || echo "0, 0, 0, 0, 0, 0, 0, 0, P0, 0, 0")
        gpu_temp=$(echo "$gpu_line" | awk -F', ' '{print $1+0}')
        gpu_power=$(echo "$gpu_line" | awk -F', ' '{print $2+0}')
        gpu_plimit=$(echo "$gpu_line" | awk -F', ' '{print $3+0}')
        gpu_fan=$(echo "$gpu_line" | awk -F', ' '{print $4+0}')
        gpu_util=$(echo "$gpu_line" | awk -F', ' '{print $5+0}')
        gpu_mem=$(echo "$gpu_line" | awk -F', ' '{print $6+0}')
        gpu_clk=$(echo "$gpu_line" | awk -F', ' '{print $7+0}')
        gpu_mem_clk=$(echo "$gpu_line" | awk -F', ' '{print $8+0}')
        gpu_pstate=$(echo "$gpu_line" | awk -F', ' '{print $9}')
        gpu_pcie_gen=$(echo "$gpu_line" | awk -F', ' '{print $10+0}')
        gpu_pcie_width=$(echo "$gpu_line" | awk -F', ' '{print $11+0}')

        # --- System load & memory (direct /proc reads, ~0ms) ---
        read -r load_1 load_5 _ < /proc/loadavg
        mem_info=$(awk '/MemTotal:/{total=$2} /MemAvailable:/{avail=$2} /SwapTotal:/{stotal=$2} /SwapFree:/{sfree=$2} END{printf "%d %d %d", (total-avail)/1024, avail/1024, (stotal-sfree)/1024}' /proc/meminfo)
        read -r mem_used mem_avail swap_used <<< "$mem_info"

        # --- Write ---
        echo "$ts,$cpu_pkg,$cpu_max,$ddr5_1,$ddr5_2,$nvme_1,$nvme_2,$gwmi_1,$gwmi_2,$gwmi_3,$gwmi_4,$gwmi_5,$gwmi_6,$gpu_temp,$gpu_power,$gpu_plimit,$gpu_fan,$gpu_util,$gpu_mem,$gpu_clk,$gpu_mem_clk,$gpu_pstate,$gpu_pcie_gen,$gpu_pcie_width,$load_1,$load_5,$mem_used,$mem_avail,$swap_used" >> "$CSV_FILE"
        samples_since_flush=$((samples_since_flush + 1))
        if (( samples_since_flush >= FLUSH_EVERY_SAMPLES )); then
          sync -d "$CSV_FILE" 2>/dev/null || true
          samples_since_flush=0
        fi

        rotate_if_needed
        sleep "$INTERVAL"
      done
    '';
  };
in
mkServiceModule {
  name = "power-watchdog";
  description = "High-frequency sensor logger for power loss forensics";
  health = {
    unit = "power-watchdog.service";
    type = "service";
    restartable = true;
  };
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Sensor polling interval in seconds.";
    };
    retentionDays = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Number of days of sensor data to retain.";
    };
    flushEverySamples = lib.mkOption {
      type = lib.types.int;
      default = 15;
      description = "Flush CSV file to disk after this many samples.";
    };
  };
  configFn =
    {
      cfg,
      pkgs,
      config,
      lib,
      ...
    }:
    {
      systemd.tmpfiles.rules = [
        "d ${dataDir} 0750 ${username} users -"
      ];

      systemd.services.power-watchdog = {
        description = "power-watchdog - Sensor logger for power loss forensics";
        wantedBy = [ "multi-user.target" ];
        after = [
          "local-fs.target"
          "lm_sensors.service"
        ];
        path = lib.optionals (config.sinnix.gpu.mode != "igpu") [
          pkgs.linuxPackages.nvidia_x11 # provides nvidia-smi for GPU telemetry
        ];

        serviceConfig = {
          Type = "simple";
          ExecStart = "${powerWatchdog}/bin/power-watchdog ${toString cfg.intervalSec} ${toString cfg.retentionDays} ${toString cfg.flushEverySamples}";
          Restart = "on-failure";
          RestartSec = "5s";
          Nice = 19;
          IOSchedulingClass = "idle";
          IOWeight = 1;
        };
      };
    };
} args
