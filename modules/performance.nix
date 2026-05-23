# Performance baseline
#
# Keep desktop-critical processes protected while build/background workloads are
# explicitly placed into lower-weight slices by `sinnix-scope`. The failed
# /cache NVMe is gone and PCIe links are currently healthy, but measurements on
# this host still show enough random-I/O tail latency that unscoped heavy work
# can starve interactive recovery paths.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  panicLogCapture = pkgs.writeShellApplication {
    name = "panic-log-capture";
    runtimeInputs = [ pkgs.coreutils ];
    text = ''
      set -eu

      out=/var/log/panic
      mkdir -p "$out"

      if [ -d /sys/fs/pstore ]; then
        for f in /sys/fs/pstore/*; do
          [ -e "$f" ] || continue
          cp -a "$f" "$out/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$f")" || true
        done
      fi
    '';
  };
  applyCpuPowerLimits = pkgs.writeShellApplication {
    name = "sinnix-apply-cpu-power-limits";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.gnugrep
    ];
    text = ''
      set -eu

      package=
      for candidate in /sys/class/powercap/intel-rapl:*; do
        [ -f "$candidate/name" ] || continue
        if grep -qx 'package-0' "$candidate/name"; then
          package="$candidate"
          break
        fi
      done

      [ -n "$package" ] || exit 0

      # This host currently reaches the 100C package critical threshold even
      # under Intel's nominal 125W/253W i7-13700K envelope. Keep a conservative
      # workstation cap until cooling is physically inspected.
      printf '%s\n' 95000000 >"$package/constraint_0_power_limit_uw"
      printf '%s\n' 150000000 >"$package/constraint_1_power_limit_uw"
    '';
  };
in
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    zramSwap = {
      enable = true;
      memoryPercent = 25;
      algorithm = "zstd";
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    boot.kernel.sysctl = {
      # Keep zram as the first emergency buffer. The root Btrfs swapfile is
      # much slower and can visibly stall interactive work under pressure.
      "vm.swappiness" = 10;
      "vm.page-cluster" = 0;
      "vm.vfs_cache_pressure" = 50;
      "vm.dirty_background_ratio" = 5;
      "vm.dirty_ratio" = 10;

      # Preserve the crash diagnostics that helped during the hardware pass.
      "kernel.hung_task_panic" = 1;
      "kernel.hung_task_timeout_secs" = 120;
      "kernel.panic" = 60;
      "kernel.oops_all_cpu_backtrace" = 1;
      "kernel.hardlockup_all_cpu_backtrace" = 1;
      "kernel.softlockup_all_cpu_backtrace" = 1;
    }
    //
      lib.optionalAttrs
        (
          lib.attrByPath [ "sinnix" "services" "sinex" "prepareHost" ] false config
          || lib.attrByPath [ "sinnix" "services" "sinex" "enable" ] false config
        )
        {
          "fs.inotify.max_user_watches" = 524288;
        };

    boot.kernelModules = [ "ramoops" ];
    boot.kernelParams = [
      "ramoops.record_size=262144"
      "ramoops.console_size=262144"
      "ramoops.ftrace_size=131072"
      "ramoops.dump_oops=1"
    ];

    systemd.services.panic-log-capture = {
      description = "Capture previous-boot kernel panic/oops logs from pstore";
      wantedBy = [ "multi-user.target" ];
      after = [ "local-fs.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${panicLogCapture}/bin/panic-log-capture";
      };
    };

    systemd.services.sinnix-cpu-power-limits = {
      description = "Apply sane Intel CPU package power limits";
      wantedBy = [ "multi-user.target" ];
      after = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${applyCpuPowerLimits}/bin/sinnix-apply-cpu-power-limits";
      };
    };

    services.earlyoom = {
      enable = true;
      enableNotifications = true;
      # Kill only near true exhaustion. With a real swapfile, earlyoom is the
      # emergency brake, not routine pressure management.
      freeMemThreshold = 5;
      freeSwapThreshold = 15;
      extraArgs = [
        "--prefer"
        "(node|python|cargo|rustc|cc1plus|ld|nix|nix-daemon)"
        "--avoid"
        "(systemd|systemd-logind|dbus-daemon|sshd|agetty|Hyprland|waybar|foot|kitty|zsh|bash|sudo|doas|below|chrome|chromium|firefox|electron)"
      ];
    };

    # Avoid systemd-oomd PSI kills while this host is being retuned. earlyoom is
    # simpler and global; it does not depend on the custom slice hierarchy that
    # was removed here.
    systemd.oomd.enable = false;

    systemd.slices = {
      background.sliceConfig = {
        CPUWeight = 10;
        IOWeight = 5;
        MemoryHigh = "4G";
        MemoryMax = "10G";
      };

      "nix-build".sliceConfig = {
        CPUWeight = 20;
        IOWeight = 10;
        MemoryHigh = "8G";
        MemoryMax = "16G";
      };
    };

    systemd.user.slices = {
      agent.sliceConfig = {
        CPUWeight = 200;
        IOWeight = 100;
        MemoryLow = "1G";
        MemoryHigh = "12G";
      };

      background.sliceConfig = {
        CPUWeight = 10;
        IOWeight = 5;
        MemoryHigh = "4G";
        MemoryMax = "10G";
      };

      build.sliceConfig = {
        CPUWeight = 20;
        IOWeight = 10;
        MemoryHigh = "8G";
        MemoryMax = "16G";
      };
    };

    security.pam.loginLimits = [
      {
        domain = "@audio";
        type = "-";
        item = "rtprio";
        value = "95";
      }
      {
        domain = "@audio";
        type = "-";
        item = "memlock";
        value = "unlimited";
      }
      {
        domain = "@audio";
        type = "-";
        item = "nice";
        value = "-11";
      }
    ];
  };
}
