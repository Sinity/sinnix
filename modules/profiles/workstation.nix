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

    # Tiered swap posture: zram is the fast first tier absorbing bursts at
    # RAM speed; the NVMe swapfile (hosts/sinnix-prime/storage.nix, priority
    # 10) is the overflow tier for sustained pressure. Telemetry samples
    # zram/PSI/refaults so a thrash regression stays visible.
    # History/evidence: bd show sinnix-mys
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      # 12 GiB, sized from a measured 3.6:1 compression ratio under real
      # load; do not raise further without a zram residue-reset hygiene step
      # (incompressible worst case approaches 1:1). Disksize changes apply
      # to /dev/zram0 only on reboot, not on a live switch.
      # History/evidence: bd show sinnix-mys
      memoryMax = 12 * 1024 * 1024 * 1024;
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    # No polkit password dialogs for wheel on service management and power
    # actions (2026-07-10, operator request). Rationale: the 2026-07-06
    # root-equivalence decision already accepts that every agent-as-sinity
    # process is root-equivalent (NOPASSWD sudo + nix trusted-users), so a
    # polkit prompt for `systemctl restart foo` is friction without a
    # security boundary behind it — the same actor can `sudo systemctl`
    # promptlessly. Scoped to systemd unit management + login1 power/session
    # actions rather than a blanket YES so genuinely unusual actions
    # (disk reformat via udisks, etc.) still surface.
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
      # swappiness=10 keeps anon memory resident and lets a brief allocation
      # burst spill to swap instead of triggering an immediate earlyoom kill,
      # without reverting to the sustained page-cache-hoarding regime that
      # higher values caused. min_free_kbytes/watermark_scale_factor below
      # hold a concrete free-page reserve for burst-alloc starvation.
      # History/evidence: bd show sinnix-mys
      "vm.swappiness" = 10;
      "vm.page-cluster" = 0;
      # vfs_cache_pressure=100 (kernel default) reclaims file cache normally;
      # a prior overshoot (1000) kept dentries/inodes permanently cold,
      # forcing PID1 alone to re-read ~390 GiB/day of unit fragments.
      # History/evidence: bd show sinnix-mys
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
      # surface in bursts. Keep inotify capacity high enough that the bus daemon
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

    # No periodic cache-drop machinery here: kernel LRU reclaim is the cache
    # bound. A former drop_caches timer manufactured the pressure it claimed
    # to relieve, since MemAvailable already counts reclaimable cache.
    # History/evidence: bd show sinnix-mys
    services.earlyoom = {
      enable = true;
      enableNotifications = true;
      # earlyoom acts only when BOTH memory and swap are below threshold; the
      # memory gate is a % of MemAvailable+AnonPages (~26 GiB on this host).
      # -m3 is the emergency floor for true exhaustion, not the first
      # responder: PSI-scoped oomd (below) and the swap tiers handle pressure
      # first, and earlyoom itself generated the kill storms as first responder.
      # History/evidence: bd show sinnix-3gb
      freeMemThreshold = 3;
      # freeSwapThreshold=50 lets a burst use up to ~4 GiB of fast NVMe/zram
      # swap before earlyoom panics, while still firing well before swap is
      # exhausted. The old ~10% default suppressed the kill until the
      # compositor was already wedged on a slower swap substrate.
      # History/evidence: bd show sinnix-3gb
      freeSwapThreshold = 50;
      extraArgs = [
        # No --prefer regex: victim steering was an arms race; at the -m3
        # floor, oom_score-based choice is fine and slice-scoped oomd handles
        # "kill the runaway build, not the desktop" at cgroup granularity.
        # Only recovery-critical surfaces are avoided — agents remain
        # eligible victims (process-name avoidance is not a containment
        # boundary; per-scope MemoryHigh/MemoryMax is).
        # History/evidence: bd show sinnix-3gb, bd show sinnix-1uo
        "--avoid"
        earlyoomAvoidPattern
      ];
    };

    systemd.services.earlyoom = {
      wants = [ "swap.target" ];
      after = [ "swap.target" ];
    };

    # systemd-oomd is the first-line kill policy: sacrificial slices
    # (build/nix-build/background) carry ManagedOOMMemoryPressure=kill at
    # 50%/30s (runtime-defaults.nix) so a wedged build dies as a cgroup
    # while the desktop and agents never qualify; earlyoom stays the global
    # emergency floor at -m3.
    # History/evidence: bd show sinnix-3gb
    systemd.oomd.enable = true;

    # Devshell/agent scratch belongs on /realm NVMe, not the RAM-backed /tmp
    # tmpfs: per-shell TMPDIR dirs never get cross-session retention pruning,
    # so heavy test fixtures accumulate and can pin tmpfs RAM. NVMe contents
    # also survive reboots, so the age-based cleanup below is load-bearing.
    # History/evidence: bd show sinnix-7yd
    environment.sessionVariables.TMPDIR = "/realm/tmp/shell";
    systemd.tmpfiles.rules = [
      "d /realm/tmp/shell 1777 root root 7d"
      # Claude Code bypasses TMPDIR for task output captures. Managed Claude
      # wrappers point CLAUDE_CODE_TMPDIR here so 12+ concurrent subagents
      # cannot fill the shared 6 GiB /tmp tmpfs again (sinnix-77w).
      "d /realm/tmp/claude-code 0700 ${user} users 7d"
      # The designated home for ad-hoc session/agent output files (bead work
      # notes, query dumps, one-off analysis). Root /realm/tmp stays unaged
      # (operator decision 2026-08-02: manual sweeps only) — the aged subdir
      # exists so new litter has somewhere to expire instead of accumulating
      # at the root forever (1,237 top-level entries >30d as of 2026-08-02).
      "d /realm/tmp/work 1777 root root 30d"
    ];

    # nix.slice has no explicit unit here: it exists only as the implicit
    # dash-hierarchy parent of nix-build.slice (systemd creates parent slices
    # automatically), and it has exactly one child, so giving it its own
    # CPUWeight/IOWeight (previously byte-identical to nix-build.slice's) had
    # no sibling to compete against and did nothing.
    systemd.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.system;

    systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.user;
  };
}
