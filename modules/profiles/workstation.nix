# Interactive workstation profile.
#
# Coarse aggregate for a desktop/interactive host (sinnix-prime). Sets
# `sinnix.machine.isDesktop = true` and owns the resource-governance stack
# that keeps desktop-critical processes protected while build/background
# workloads are explicitly placed into lower-weight slices by
# `sinnix-scope`: systemd slices, earlyoom policy, io.cost init, RAPL power
# caps, and the interactive memory sysctls.
#
# Mirrors modules/profiles/cloud.nix's shape (enable-gated aggregate a host
# opts into) rather than scattering `isDesktop` conditionals across modules.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.profiles.workstation;
  runtimeInventory = config.sinnix.runtime.inventory;
  user = config.sinnix.user.name;
  earlyoomAvoidPattern = runtimeInventory.earlyoomEmergencyAvoidPattern;
  forbiddenEarlyoomAvoidTokens = [
    "bash"
    "chrome"
    "chromium"
    "claude"
    "codex"
    "electron"
    "firefox"
    "node"
    "python"
    "zsh"
  ];
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
  options.sinnix.profiles.workstation.enable = lib.mkEnableOption "Interactive workstation profile";

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = lib.all (
          token: !(lib.hasInfix token earlyoomAvoidPattern)
        ) forbiddenEarlyoomAvoidTokens;
        message = "earlyoom must not exempt agents, browsers, language runtimes, or generic shells";
      }
      {
        assertion = lib.hasInfix "start-hyprland" earlyoomAvoidPattern;
        message = "earlyoom must protect the lowercase Hyprland session launcher used by UWSM";
      }
    ];

    sinnix.machine.isDesktop = lib.mkForce true;

    # Tiered swap posture (operator axiom "things getting killed >> thrash"):
    # zram is the fast first tier that absorbs allocation bursts at RAM
    # speed, the NVMe swapfile (hosts/sinnix-prime/storage.nix, priority 10)
    # is the overflow tier for sustained pressure. An 8 GiB zram device costs
    # ~20 MiB until used and ~1 byte per ~3 bytes of cold anon it holds
    # (zstd); machine-telemetry samples zram mm_stat, per-device swap
    # occupancy, PSI, and refaults, so a thrash regression is visible within
    # hours.
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      # 12G costs ~3.3G resident when full at the measured 3.6:1 ratio and
      # widens the burst absorber; do not go past ~12G on 32G RAM without a
      # zram residue-reset hygiene (dead post-build pages park compressed
      # until faulted or reset) because the incompressible worst case
      # approaches 1:1. Disksize change applies to /dev/zram0 on reboot;
      # a live switch cannot resize an active swap device.
      memoryMax = 12 * 1024 * 1024 * 1024;
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    # No polkit password dialogs for wheel on service management and power
    # actions. Rationale: the agent root-equivalence decision already accepts
    # that every agent-as-sinity process is root-equivalent (NOPASSWD sudo +
    # nix trusted-users), so a polkit prompt for `systemctl restart foo` is
    # friction without a security boundary behind it — the same actor can
    # `sudo systemctl` promptlessly. Scoped to systemd unit management +
    # login1 power/session actions rather than a blanket YES so genuinely
    # unusual actions (disk reformat via udisks, etc.) still surface.
    security.polkit.extraConfig = ''
      polkit.addRule(function(action, subject) {
        if (!subject.isInGroup("wheel")) return undefined;
        if (action.id.indexOf("org.freedesktop.systemd1.") === 0) {
          return polkit.Result.YES;
        }
        if (action.id.indexOf("org.freedesktop.login1.") === 0) {
          return polkit.Result.YES;
        }
        return undefined;
      });
    '';

    boot.kernel.sysctl = {
      # Keep process (anon) memory resident; reclaim file cache before swapping,
      # and start reclaim early enough that interactive work sees real free
      # pages instead of relying on last-second cache eviction. A brief
      # allocation burst should be absorbed by swap rather than triggering an
      # immediate earlyoom kill; a small nonzero swappiness lets the kernel
      # prefer that over letting a transient spike go straight to a kill,
      # without reverting to a heavy-swap-hoarding regime that hoards page
      # cache instead of reclaiming it. Maintain a concrete free-page reserve
      # (min_free_kbytes + watermark_scale_factor) so "available" memory does
      # not depend on painful last-second reclaim.
      "vm.swappiness" = 10;
      "vm.page-cluster" = 0;
      # vfs_cache_pressure=100 (kernel default) keeps dentries/inodes
      # reclaimable at a normal rate; a much higher value suppresses VFS
      # caches enough that PID1 and other frequent unit/library readers
      # re-read the same fragments from disk repeatedly. Burst headroom is
      # owned by min_free_kbytes + watermark_scale_factor below, not by
      # suppressing the VFS caches.
      "vm.vfs_cache_pressure" = 100;
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

    # There is deliberately NO periodic cache-drop machinery here.
    # `sync; echo 3 > drop_caches` on a timer manufactures the very pressure
    # it claims to relieve (millions of workingset refaults, terabytes/day of
    # re-reads) because MemAvailable already counts reclaimable cache as
    # available; kernel LRU reclaim is the cache bound.
    services.earlyoom = {
      enable = true;
      enableNotifications = true;
      # earlyoom acts only when BOTH memory and swap are below threshold.
      # Keep the memory gate tied to real MemAvailable pressure. earlyoom
      # v1.9 computes this percentage against "user mem total"
      # (MemAvailable + AnonPages), which is ~26 GiB on sinnix-prime under
      # current desktop load; 5% is about 1.3 GiB of MemAvailable headroom.
      # With PSI-scoped oomd killing wedged sacrificial slices
      # (runtime-defaults.nix) and the zram+NVMe swap tiers absorbing
      # bursts, earlyoom is the emergency floor for true exhaustion, not the
      # first responder: zero kernel OOMs have ever been recorded, so a
      # low threshold buys margin without earlyoom preempting oomd/swap.
      freeMemThreshold = 3;
      # freeSwapThreshold=100 makes the swap condition a no-op (any nonzero
      # swap usage satisfies "below 100% free"), so earlyoom fires the
      # instant MemAvailable alone dips under freeMemThreshold regardless of
      # idle swap capacity — appropriate only when swap itself is slow or
      # contended. With swap on fast NVMe and vm.swappiness=10, a lower
      # threshold lets a burst use swap capacity (up to ~4 GiB here) before
      # earlyoom panics, while still acting well before swap nears
      # exhaustion.
      freeSwapThreshold = 50;
      extraArgs = [
        # No --prefer regex: at the -m3 floor earlyoom only fires at true
        # exhaustion, where oom_score-based choice is appropriate. Slice-
        # scoped oomd handles the "kill the runaway build, not the desktop"
        # case at cgroup granularity.
        #
        # Protect only recovery-critical surfaces. Agents are isolated by
        # finite per-scope MemoryHigh/MemoryMax limits and intentionally
        # remain eligible here: process-name avoidance is not a containment
        # boundary, and a runaway agent child can retain an unrelated comm
        # name while consuming double-digit GiB RSS, making earlyoom kill
        # many small unrelated processes before reaching the actual hog.
        "--avoid"
        earlyoomAvoidPattern
      ];
    };

    systemd.services.earlyoom = {
      wants = [ "swap.target" ];
      after = [ "swap.target" ];
    };

    # systemd-oomd is the first-line kill policy: sacrificial slices
    # (build/nix-build/background, both scopes) carry
    # ManagedOOMMemoryPressure=kill at 50%/30s in runtime-defaults.nix, so a
    # wedged build dies as a cgroup while the desktop and agents never
    # qualify — the 50%/30s gate only fires on scopes that are genuinely
    # stalled on their own memory (a 10%/5s gate is too aggressive and kills
    # scopes under merely transient pressure). earlyoom remains the global
    # emergency floor at -m3.
    systemd.oomd.enable = true;

    # Devshell/agent scratch belongs on /realm NVMe, not the RAM-backed /tmp
    # tmpfs. `nix develop` creates its per-shell TMPDIR (nix-shell.XXXXXX)
    # under the ambient TMPDIR, and heavy test suites (lynchpin pytest duckdb
    # fixtures) write GiBs there; every shell gets a fresh dir, so per-tool
    # retention (e.g. pytest's keep-last-3) never prunes across sessions and
    # accumulated dirs can pin the whole /tmp tmpfs as unreclaimable shmem.
    # Pointing the session TMPDIR at NVMe keeps /tmp tmpfs for small system
    # churn while shell/test scratch lands on wear-tolerant storage with
    # age-based cleanup (the `7d` field below; NVMe contents also survive
    # reboots, unlike tmpfs, hence the aging is load-bearing).
    environment.sessionVariables.TMPDIR = "/realm/tmp/shell";
    systemd.tmpfiles.rules = [
      "d /realm/tmp/shell 1777 root root 7d"
      # Claude Code bypasses TMPDIR for task output captures. Managed Claude
      # wrappers point CLAUDE_CODE_TMPDIR here so many concurrent subagents
      # cannot fill the shared /tmp tmpfs.
      "d /realm/tmp/claude-code 0700 ${user} users 7d"
      # The designated home for ad-hoc session/agent output files (bead work
      # notes, query dumps, one-off analysis). Root /realm/tmp stays unaged
      # (manual sweeps only) — the aged subdir exists so new litter has
      # somewhere to expire instead of accumulating at the root forever.
      "d /realm/tmp/work 1777 root root 30d"
    ];

    # nix.slice has no explicit unit here: it exists only as the implicit
    # dash-hierarchy parent of nix-build.slice (systemd creates parent slices
    # automatically), and it has exactly one child, so giving it its own
    # CPUWeight/IOWeight has no sibling to compete against and does nothing.
    systemd.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.system;

    systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.user;
  };
}
