# Interactive workstation profile.
#
# Coarse aggregate for a desktop/interactive host (sinnix-prime). Sets
# `sinnix.machine.isDesktop = true` and owns the resource-governance stack
# that keeps desktop-critical processes protected while declared services and
# AgentCTL jobs receive their own resource policy: systemd slices, earlyoom
# policy, io.cost init, RAPL power
# caps, the interactive memory sysctls, and the bounded stop timeout that
# keeps one wedged session unit from owning the whole reboot.
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
        echo "$dev" | grep -q "^loop" && continue
        [ -f "$dev_path/queue/scheduler" ] || continue

        major_minor=$(cat "$dev_path/dev")

        scheduler=$(cat "$dev_path/queue/scheduler")
        if echo "$scheduler" | grep -q "\[none\]"; then
          echo "mq-deadline" > "$dev_path/queue/scheduler" || true
        fi

        # Auto-calibrate the cost model from device latency, making IOWeight
        # proportional and work-conserving rather than nominal.
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
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      # 12 GiB, sized from a measured 3.6:1 compression ratio under real
      # load; do not raise further without a zram residue-reset hygiene step
      # (incompressible worst case approaches 1:1). Disksize changes apply
      # to /dev/zram0 only on reboot, not on a live switch.
      memoryMax = 12 * 1024 * 1024 * 1024;
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    # No polkit password dialogs for wheel on unit management and power
    # actions: wheel already has NOPASSWD sudo, so the prompt is friction with
    # no security boundary behind it. Deliberately scoped to systemd1 and
    # login1 rather than a blanket YES, so genuinely unusual actions (disk
    # reformat via udisks, etc.) still surface.
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
      # burst spill to swap instead of triggering an immediate earlyoom kill;
      # higher values cause sustained page-cache hoarding.
      # min_free_kbytes/watermark_scale_factor hold a concrete free-page
      # reserve against burst-alloc starvation.
      "vm.swappiness" = 10;
      "vm.page-cluster" = 0;
      # Kernel default; do not raise. At 1000 dentries/inodes stay permanently
      # cold and PID1 alone re-reads hundreds of GiB/day of unit fragments.
      "vm.vfs_cache_pressure" = 100;
      "vm.min_free_kbytes" = 1048576;
      "vm.watermark_scale_factor" = 200;
      # Keep Btrfs/NVMe writeback from accumulating multi-GiB dirty bursts:
      # the Crucial P3 /realm drive shows 30s NVMe command timeouts under
      # mixed build/database writeback, and bounded dirty bytes push back
      # earlier, making stalls shorter and more attributable.
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

    # No periodic cache-drop machinery: kernel LRU reclaim is the cache bound,
    # and a drop_caches timer manufactures the pressure it claims to relieve
    # since MemAvailable already counts reclaimable cache.
    services.earlyoom = {
      enable = true;
      enableNotifications = true;
      # earlyoom acts only when memory AND swap are below threshold AND the
      # machine is actually stalling (--mem-psi-min, sinnix patch). The
      # memory gate is a % of physical MemTotal (overlay patch), ~1 GiB
      # here. -m3 is the emergency floor for true exhaustion, not the first
      # responder — PSI-scoped oomd (below) and the swap tiers handle
      # pressure first. As first responder earlyoom produces kill storms.
      freeMemThreshold = 3;
      # Free-swap minimum: fire only once swap is genuinely nearly exhausted
      # (<10% free ≈ 2 GiB of 20 GiB). The former 50 never bound — swap sits
      # above 50% used for most of any active day, so the intended
      # memory-AND-swap conjunction had collapsed to a bare free-memory
      # trigger (2026-08-18 incident taxonomy; 98-day record).
      freeSwapThreshold = 10;
      extraArgs = [
        # No --prefer regex: at the -m3 floor oom_score-based choice is fine,
        # and slice-scoped oomd handles "kill the runaway build, not the
        # desktop" at cgroup granularity. Only recovery-critical surfaces are
        # avoided — agents stay eligible victims, since process-name avoidance
        # is not a containment boundary (per-scope MemoryHigh/Max is).
        "--avoid"
        earlyoomAvoidPattern
        # At the memory-and-swap emergency floor, sustained full-memory PSI
        # above 10 already makes the graphical session unreliable.
        "--mem-psi-min"
        "10"
      ];
    };

    systemd.services.earlyoom = {
      wants = [ "swap.target" ];
      after = [ "swap.target" ];
    };

    # systemd-oomd is the first-line kill policy: sacrificial slices
    # Sacrificial workload slices carry their own pressure policy; earlyoom
    # remains the global emergency floor at -m3.
    systemd.oomd.enable = true;

    # Devshell/agent scratch belongs on /realm NVMe, not the RAM-backed /tmp
    # tmpfs: per-shell TMPDIR dirs get no cross-session pruning, so heavy test
    # fixtures accumulate and can pin tmpfs RAM. NVMe contents survive
    # reboots, which is what makes the age-based cleanup below load-bearing.
    environment.sessionVariables.TMPDIR = "/realm/tmp/shell";
    systemd.tmpfiles.rules = [
      "d /realm/tmp/shell 1777 root root 7d"
      # Claude Code bypasses TMPDIR for task output captures. Managed Claude
      # wrappers point CLAUDE_CODE_TMPDIR here so concurrent subagents cannot
      # fill the shared 6 GiB /tmp tmpfs.
      "d /realm/tmp/claude-code 0700 ${user} users 7d"
      # The designated home for ad-hoc session/agent output files (bead work
      # notes, query dumps, one-off analysis). Root /realm/tmp stays unaged by
      # operator decision — manual sweeps only — so this aged subdir gives new
      # litter somewhere to expire instead of accumulating at the root.
      "d /realm/tmp/work 1777 root root 30d"
    ];

    # nix.slice has no explicit unit: it exists only as the implicit
    # dash-hierarchy parent systemd creates for nix-build.slice, and with a
    # single child its own CPUWeight/IOWeight would have no sibling to compete
    # against.
    systemd.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.system;

    systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.user;

    # Shutdown cost of the graphical session is bounded here, once, for every
    # user unit — Sinnix-owned or not.
    #
    # The tty1 login parks `systemctl --user start --wait
    # wayland-session-envelope@hyprland-uwsm.desktop.target` inside
    # session-1.scope (uwsm's signal-handler.sh, which on SIGTERM stops that
    # target and then waits on the same pid). logind stops the session scope
    # BEFORE the user manager — user@1000.service is ordered
    # Before=session-1.scope, and ordering reverses on stop — so the scope's
    # stop job completes only once the envelope target, and therefore every
    # graphical-session member, has gone inactive. One member that ignores
    # SIGTERM holds the target for its full stop timeout while the session
    # scope burns an identical timeout in parallel, and logind offers no
    # per-scope knob to cap a transient session scope: it inherits the manager
    # default. Bounding that default is the only lever that reaches the whole
    # chain.
    #
    # Measured, not theorised: the 2026-08-14 reboot cost 91s of dead time
    # because a single wedged screen recorder sat in graphical-session.target
    # for the full 90s default. That unit is gone, but the exposure was never
    # specific to it — 44 of the 47 user services running on this host carry
    # the 90s default, so any one of them can reproduce the stall.
    #
    # 15s is Sinnix's established shutdown-debris cap for ordinary services,
    # Borg jobs, and Sinex maintenance timers.
    # A session helper still alive 15s after SIGTERM is wedged; the choice is
    # not between a clean exit and a kill, it is between killing it now and
    # killing it 75s later. This is only the *default*, so per-unit
    # TimeoutStopSec still wins in either direction — the three user services
    # that already declare their own keep them (uwsm's wayland-wm@ at 10s,
    # nm-applet and at-spi at 5s) — and the system manager's own 90s default
    # is deliberately left alone, since daemons with real flush work sit
    # outside this chain.
    systemd.user.settings.Manager.DefaultTimeoutStopSec = "15s";
  };
}
