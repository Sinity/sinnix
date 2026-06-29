# Performance baseline
#
# Keep desktop-critical processes protected while build/background workloads are
# explicitly placed into lower-weight slices by `sinnix-scope`. Root-backed
# build scratch and bounded slice budgets are the current baseline; /realm stays
# data/capture storage rather than latency-sensitive build workspace.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  runtimeInventory = config.sinnix.runtime.inventory;
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
  iocostInit = pkgs.writeShellApplication {
    name = "sinnix-iocost-init";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.gnugrep
    ];
    text = ''
      set -eu

      # io.cost makes IOWeight declarations in the cgroup hierarchy actually
      # effective on NVMe drives. Without it, the kernel ignores IOWeight for
      # any device running the 'none' (passthrough) scheduler — which is the
      # NVMe default — so every IOWeight config in the slice tree is silently
      # discarded. Setting the scheduler to mq-deadline lets the block layer
      # mediate between cgroups, and ctrl=auto calibrates the cost model from
      # the device's actual latency characteristics.
      for dev_path in /sys/block/*/; do
        dev=$(basename "$dev_path")
        # Skip loop devices
        echo "$dev" | grep -q "^loop" && continue
        # Skip if no queue/scheduler
        [ -f "$dev_path/queue/scheduler" ] || continue

        major_minor=$(cat "$dev_path/dev")

        # NVMe uses 'none' by default which disables queue-based IO scheduling.
        # Switch to mq-deadline so cgroup IOWeight can actually take effect.
        scheduler=$(cat "$dev_path/queue/scheduler")
        if echo "$scheduler" | grep -q "\[none\]"; then
          echo "mq-deadline" > "$dev_path/queue/scheduler" || true
        fi

        # Activate iocost cost model — auto-calibrates from device latency.
        # This makes IOWeight proportional and work-conserving rather than nominal.
        printf '%s enable=1 ctrl=auto\n' "$major_minor" > /sys/fs/cgroup/io.cost.qos || true
      done
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

      # Keep the desktop thermal envelope below the i7-13700K's package
      # critical threshold during sustained compile and media workloads.
      printf '%s\n' 95000000 >"$package/constraint_0_power_limit_uw"
      printf '%s\n' 150000000 >"$package/constraint_1_power_limit_uw"
    '';
  };
in
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    # zram is the ONLY swap on this host (2026-06-12): both disk swapfiles were
    # deleted (see hosts/sinnix-prime/storage.nix). The 2026-06-07 zram failure
    # was a swappiness=60 + disk-spill problem — zram filled, then anon still
    # paged to the disk swapfile. With swappiness=1 AND no disk swap to spill
    # to, that path is gone: this small RAM-backed (zstd-compressed) cushion
    # absorbs short allocation spikes without touching either SSD. Capped at
    # 4 GiB so it can never grow into a large pressure sink that delays earlyoom.
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      memoryPercent = 50;
      memoryMax = 4 * 1024 * 1024 * 1024; # hard cap → effective size = 4 GiB
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    boot.kernel.sysctl = {
      # Keep process (anon) memory resident; reclaim file cache before swapping,
      # and start reclaim early enough that interactive work sees real free
      # pages instead of relying on last-second cache eviction.
      # Diagnosed 2026-06-07: swappiness=60 + vfs_cache_pressure=50 made the box
      # hoard ~18 GiB page cache while paging ~17 GiB of anon to swap (incl.
      # ~9 GiB to the disk swapfile) despite ~20 GiB available RAM. swappiness=1
      # + vfs_cache_pressure=100 inverted that path. The 2026-06-29 agent/build
      # failure mode was different: truly-free pages were low, zram was full,
      # and new rustc processes needed multi-GiB allocations immediately.
      # Maintain a concrete free-page reserve and apply stronger VFS pressure so
      # "available" memory does not depend on painful last-second reclaim.
      "vm.swappiness" = 1;
      "vm.page-cluster" = 0;
      "vm.vfs_cache_pressure" = 200;
      "vm.min_free_kbytes" = 1048576;
      "vm.watermark_scale_factor" = 200;
      # Keep Btrfs/NVMe writeback from accumulating multi-GiB dirty bursts.
      # The Crucial P3 /realm drive has shown 30s NVMe command timeouts under
      # mixed build/database writeback; bounded dirty bytes push back earlier
      # and make stalls shorter and more attributable.
      "vm.dirty_background_bytes" = 64 * 1024 * 1024;
      "vm.dirty_bytes" = 256 * 1024 * 1024;

      # Rebuild and Home Manager activation reload a large user unit/D-Bus
      # surface in bursts. Keep inotify capacity high enough that dbus-broker
      # and the user manager can attach their watches instead of timing out
      # during switch activation.
      "fs.inotify.max_user_watches" = 2097152;
      "fs.inotify.max_user_instances" = 65536;
      "fs.inotify.max_queued_events" = 262144;

      # Preserve crash diagnostics without turning ordinary hung-task reports
      # into automatic workstation reboots.
      "kernel.hung_task_panic" = 0;
      "kernel.hung_task_timeout_secs" = 120;
      "kernel.panic" = 60;
      "kernel.oops_all_cpu_backtrace" = 1;
      "kernel.hardlockup_all_cpu_backtrace" = 1;
      "kernel.softlockup_all_cpu_backtrace" = 1;
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

    systemd.services.sinnix-iocost-init = {
      description = "Activate io.cost on all block devices so IOWeight is honoured";
      wantedBy = [ "sysinit.target" ];
      before = [ "sysinit.target" ];
      unitConfig.DefaultDependencies = false;
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${iocostInit}/bin/sinnix-iocost-init";
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
      # Act before multi-GiB disk-swap residency turns into sustained major
      # faults and Btrfs queue collapse. Build/background slices stay weighted
      # and capped, but oomd does not kill them on PSI alone.
      # Fire early on memory pressure, before swap gets meaningfully used.
      # 15% of 32 GiB = ~5 GiB free — kills misbehaving processes while the
      # system is still responsive. Swap is a last-ditch cushion, not a sink.
      freeMemThreshold = 15;
      # Fire as soon as the zram cushion starts filling — 90% free on the 4 GiB
      # zram = ~400 MiB used. Combined with the memory threshold this ensures
      # earlyoom acts on memory pressure alone, before the compressed cushion is
      # churned (and there is no disk swap to fall back to).
      freeSwapThreshold = 90;
      extraArgs = [
        # Prefer killing heavy build tooling under pressure — NOT the coding
        # agents. `node`/`python` were removed here: Claude Code is a `node`
        # process and the MCP servers are `node`/`python`, so preferring them
        # made earlyoom kill the running agent (and its MCPs) whenever a second
        # agent was launched.
        "--prefer"
        "(cargo|rustc|cc1plus|ld|nix|nix-daemon)"
        # Protect interactive surfaces. Coding agents (`claude`, `codex`, and
        # their `node` runtime/MCP children) are interactive work and are
        # avoided like the desktop apps so launching one never evicts another.
        "--avoid"
        "(systemd|systemd-logind|dbus-daemon|sshd|agetty|Hyprland|noctalia|quickshell|foot|kitty|zsh|bash|sudo|doas|below|chrome|chromium|firefox|electron|claude|codex|node)"
      ];
    };

    # Keep systemd-oomd enabled at the platform level, but Sinnix's own
    # build/background policy intentionally does not use PSI-triggered kills.
    # Earlier measurements showed false-positive kills with plenty of memory
    # available; earlyoom remains the global emergency fallback.
    systemd.oomd.enable = true;

    systemd.slices =
      (lib.mapAttrs (_: sliceConfig: {
        inherit sliceConfig;
      }) runtimeInventory.slices.system)
      // {
        nix.sliceConfig = {
          CPUWeight = 5;
          IOWeight = 2;
        };
      };

    systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.user;

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
