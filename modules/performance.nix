# Performance Tuning
#
# Philosophy: the desktop and recovery paths get explicit cgroup protection;
# build/maintenance work gets low priority and pressure-based shedding. This
# keeps throughput opportunistic when the machine is idle without letting a
# fan-out build turn interactive shells, Waybar, Hyprland, or PID 1 into reclaim
# victims. A small disk swapfile (declared in the host storage module) stays as
# a release valve for genuinely cold pages; zram stays disabled because it burns
# CPU during the exact pressure cascade we need to break.
{
  pkgs,
  lib,
  config,
  helpers,
  ...
}:
let
  resourceBudgets = import ./lib/resource-budgets.nix;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  buildBudget = resourceBudgets.developerWork.sliceConfig;
  graphicalBudget = resourceBudgets.graphical.sliceConfig;
  # cgroup-v2 io.latency is work-conserving: low-priority peers are throttled
  # only while a protected peer is missing its target. Targets are intentionally
  # conservative first-pass values for sinnix-prime's current desktop storage:
  # root/persist/Nix on SATA SSD, cache on Samsung 960 EVO NVMe, and realm on
  # CT4000P3 NVMe. Planned test: run the Nix max-jobs benchmark matrix
  # (6/8/12/24 with cores=0) while collecting wall time, peak RSS, PSI,
  # `/sys/fs/cgroup/.../io.stat` avg_lat for these slices, and a simple desktop
  # latency probe. Re-tune these targets from that evidence instead of guessing.
  interactiveIoLatencyTargets = [
    "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 75ms"
    "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 25ms"
    "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 25ms"
  ];
  opportunisticIoLatencyTargets = [
    "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 250ms"
    "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 100ms"
    "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 100ms"
  ];
  pressureKillBudget = {
    ManagedOOMMemoryPressure = "kill";
    ManagedOOMMemoryPressureLimit = "10%";
    ManagedOOMMemoryPressureDurationSec = "5s";
  };
  opportunisticBuildBudget = buildBudget // pressureKillBudget;
  systemInteractiveBudget = {
    CPUWeight = 1000;
    IOWeight = 1000;
    IODeviceLatencyTargetSec = interactiveIoLatencyTargets;
    ManagedOOMPreference = "avoid";
    MemoryMin = "1G";
    MemoryLow = "2G";
  };
  userInteractiveBudget = {
    CPUWeight = 1000;
    IOWeight = 1000;
    IODeviceLatencyTargetSec = interactiveIoLatencyTargets;
    ManagedOOMPreference = "avoid";
    MemoryMin = "2G";
    MemoryLow = "12G";
    TasksMax = "10000";
  };
  appInteractiveBudget = graphicalBudget // {
    IODeviceLatencyTargetSec = interactiveIoLatencyTargets;
    ManagedOOMPreference = "avoid";
    MemoryMin = "1G";
    MemoryLow = "8G";
  };
  sessionInteractiveBudget = {
    ManagedOOMPreference = "avoid";
    MemoryMin = "1G";
    MemoryLow = "2G";
    CPUWeight = 1000;
    IOWeight = 1000;
    IODeviceLatencyTargetSec = interactiveIoLatencyTargets;
  };
  latencySheddingBudget = {
    IODeviceLatencyTargetSec = opportunisticIoLatencyTargets;
  };
  maintenanceGate = unit: "${scriptPkgs.sinnix-maintenance-gate}/bin/sinnix-maintenance-gate ${unit}";
  maintenanceServiceConfig = unit: {
    Slice = "sinnix-maintenance.slice";
    Nice = 19;
    CPUSchedulingPolicy = "idle";
    IOSchedulingClass = "idle";
    CPUWeight = 10;
    IOWeight = 1;
    IODeviceLatencyTargetSec = opportunisticIoLatencyTargets;
    ExecCondition = lib.mkDefault (maintenanceGate unit);
  };
in
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    # zram is disabled: under sustained pressure it burns CPU compressing
    # pages without ever freeing real memory, which is exactly the freeze
    # pattern we are trying to eliminate.
    zramSwap.enable = false;

    systemd.settings.Manager = {
      StatusUnitFormat = "name";
    };

    boot.kernel.sysctl = {
      # Disk swap is a last-resort release valve, not the default landing
      # zone. swappiness=1 keeps the kernel from preemptively pushing
      # anonymous pages out under mild pressure.
      "vm.swappiness" = 1;
      # No zram now, but a low cluster still helps disk swap latency on NVMe.
      "vm.page-cluster" = 0;
      # Keep inode/dentry cache hot — NixOS store paths are long and frequently
      # resolved. Reducing eviction pressure improves terminal startup latency.
      "vm.vfs_cache_pressure" = 50;
      # Flush dirty pages earlier to avoid bursty I/O spikes.
      "vm.dirty_background_ratio" = 5;
      "vm.dirty_ratio" = 10;
      # Hung-task stall breaker: if any task is stuck in D-state for 120s,
      # panic and reboot. Better to lose 2 minutes of work than stay wedged
      # with all terminals unresponsive. Sets the timeout low (default 120s
      # still fires — we just want the panic to follow within 60s).
      "kernel.hung_task_panic" = 1;
      "kernel.hung_task_timeout_secs" = 120;
      "kernel.panic" = 60;
      # Panic backtrace: log a full stack trace on oops/panic so pstore
      # captures actionable diagnostics (which function was stuck in D-state).
      "kernel.oops_all_cpu_backtrace" = 1;
      "kernel.hardlockup_all_cpu_backtrace" = 1;
      "kernel.softlockup_all_cpu_backtrace" = 1;
    }
    //
      lib.optionalAttrs
        (
          config.sinnix.services.sinex.prepareHost
          || config.sinnix.services.sinex.enable
          || config.sinnix.services.sinex.provisionDatabase
        )
        {
          # Filesystem capture needs a higher inotify watch budget than the desktop
          # default. Keep the tuning with the rest of the host kernel policy.
          "fs.inotify.max_user_watches" = 524288;
        };

    # pstore: persist kernel panic/oops logs across reboots.
    # After a panic, the kernel stores dmesg in a reserved RAM region
    # (ramoops / pstore). On next boot, panic-log-capture.service copies
    # them to /realm/data/captures/syslog/panic/ for post-mortem analysis.
    boot.kernelModules = [ "ramoops" ];
    boot.kernelParams = [
      "ramoops.record_size=262144"
      "ramoops.console_size=262144"
      "ramoops.ftrace_size=131072"
      "ramoops.dump_oops=1"
    ];

    systemd.services.panic-log-capture = {
      description = "Capture kernel panic/oops logs from pstore to persistent storage";
      after = [ "realm.mount" ];
      requires = [ "realm.mount" ];
      serviceConfig.Type = "oneshot";
      script = builtins.readFile ./panic-log-capture.sh;
      wantedBy = [ "multi-user.target" ];
    };

    # earlyoom: sub-second guardian. Polls /proc/meminfo at ~100ms and
    # SIGTERMs/SIGKILLs the highest oom_score process before the desktop
    # has a chance to lock. Tunables below mirror upstream defaults except
    # for the avoid/prefer regexes, which keep the compositor + shells
    # alive while pushing the killer at large dev workloads.
    services.earlyoom = {
      enable = true;
      # SIGTERM at 15% available, SIGKILL at 8%.
      # Raised from 10/5 because by 12% the system is already swap-thrashing
      # (borg backup I/O + browser/terminal memory compete for NVMe bandwidth).
      # Killing earlier prevents the desktop-freeze cascade.
      freeMemThreshold = 15;
      freeMemKillThreshold = 8;
      # Same for swap, with a wider TERM band since swap fills slowly.
      freeSwapThreshold = 20;
      freeSwapKillThreshold = 10;
      # Print a status line every 60s so journald has a trail when kills happen.
      reportInterval = 60;
      extraArgs = [
        # Never kill the compositor stack, login session, or recovery shells.
        "--avoid"
        "^(systemd|systemd-.*|Hyprland|sway|gnome-shell|kwin|Xorg|sshd|kitty|foot|bash|zsh|tmux|waybar|tofi)$"
        # Prefer to kill big memory hogs that we can always restart.
        "--prefer"
        "^(electron|chrome|chromium|firefox|node|cargo|rustc|ld|ld\\.lld|ld\\.mold|cc1|cc1plus|nix|nix-build|cmake|ninja|monado|wivrn|claude|codex|gemini|forge|nats-server)$"
      ];
    };

    # systemd-oomd is not a global desktop killer here. It only acts on slices
    # that opt in below, so opportunistic build/maintenance work is shed when
    # it is memory-stalled while interactive slices remain protected.
    systemd.oomd = {
      enable = true;
      enableRootSlice = false;
      enableSystemSlice = false;
      enableUserSlices = false;
      settings.OOM.DefaultMemoryPressureDurationSec = "5s";
    };

    # Protect PID 1's system services and login plumbing from build pressure.
    systemd.slices.system.sliceConfig = systemInteractiveBudget;

    # Keep a protected floor for the logged-in user. This is not a throughput
    # cap: build/background children can use the memory while it is free, but
    # reclaim preferentially takes it back from them before the compositor,
    # Waybar, terminals, and the user manager become unrecoverable.
    #
    # TasksMax prevents PID-space exhaustion: a thread-exploding build or fork
    # bomb inside user.slice leaves enough PIDs for recovery shells.
    systemd.slices.user.sliceConfig = userInteractiveBudget;

    # User-manager background/graphical slices use weights for proportional
    # priority, not hard ceilings. Parent `memory.high`/`memory.max` caps caused
    # desktop throttling around 75% RAM even while the machine still had free
    # memory and page cache to reclaim.
    systemd.user.slices = {
      background.sliceConfig = opportunisticBuildBudget // latencySheddingBudget;

      # Waybar and terminal windows live under app.slice on this workstation.
      # Protect enough baseline to launch a fresh terminal during pressure.
      app.sliceConfig = appInteractiveBudget;

      # Hyprland, Xwayland, portals, and the session envelope live here.
      session.sliceConfig = sessionInteractiveBudget;

      # Explicitly scoped interactive build/test entrypoints land here.
      build.sliceConfig = opportunisticBuildBudget // latencySheddingBudget;
    };

    # Root-level peer latency targets. `nix-build.slice` is nested below
    # `nix.slice`, and `sinnix-maintenance.slice` below `sinnix.slice`; set the
    # parent peer targets as well or user.slice cannot directly protect itself
    # from those workloads.
    systemd.slices.nix = {
      description = "Parent slice for Nix build work";
      sliceConfig = latencySheddingBudget;
    };
    systemd.slices.sinnix = {
      description = "Parent slice for Sinnix-managed background work";
      sliceConfig = latencySheddingBudget;
    };

    # Put Nix builds in an explicitly weighted slice so they are visible and
    # lower priority than the desktop without imposing arbitrary throughput or
    # CPU ceilings.
    #
    # Do not casually reintroduce IOReadBandwidthMax/IOWriteBandwidthMax here:
    # past caps protected bad moments by wasting idle-device capacity. If
    # weights are insufficient for browser/terminal latency, the next candidate
    # to benchmark is systemd's IODeviceLatencyTargetSec, which maps to the
    # kernel cgroup-v2 io.latency controller and is work-conserving when the
    # protected peer meets its measured latency target.
    systemd.slices."nix-build" = {
      description = "Resource budget for Nix builds";
      sliceConfig = opportunisticBuildBudget // latencySheddingBudget;
    };

    # Generic background scopes should inherit the same low-priority budget as
    # Nix builds so wrappers like `nix-safe` and future backgrounded dev tasks
    # do not run at full desktop priority by accident.
    systemd.slices.background = {
      description = "Resource budget for background developer work";
      sliceConfig = opportunisticBuildBudget // latencySheddingBudget;
    };

    systemd.slices."sinnix-maintenance" = {
      description = "Serialized low-priority maintenance work";
      sliceConfig =
        opportunisticBuildBudget
        // latencySheddingBudget
        // {
          IOWeight = 1;
          CPUWeight = 10;
          ManagedOOMMemoryPressureLimit = "5%";
        };
    };

    # The slices above are the source of truth. Helper wrappers should target
    # the correct slice instead of re-stating the whole resource envelope.
    systemd.services.nix-daemon.serviceConfig = {
      Slice = "nix-build.slice";
    }
    // opportunisticBuildBudget
    // latencySheddingBudget;

    # home-manager-${user}.service is the actual file-linker; it is pulled in
    # by switch-to-configuration but runs as its own system unit, so the parent
    # slice does not propagate. Do not define
    # nixos-rebuild-switch-to-configuration.service here: nixos-rebuild-ng
    # creates that name as a transient unit, and any static fragment makes
    # systemd-run refuse the activation job.
    systemd.services."home-manager-${config.sinnix.user.name}".serviceConfig.Slice = "nix-build.slice";

    systemd.services.nix-gc = {
      restartIfChanged = false;
      serviceConfig = maintenanceServiceConfig "nix-gc.service";
    };
    systemd.timers.nix-gc.timerConfig.Persistent = lib.mkForce false;

    systemd.services.nix-optimise = {
      restartIfChanged = false;
      serviceConfig = maintenanceServiceConfig "nix-optimise.service";
    };
    systemd.timers.nix-optimise.timerConfig.Persistent = lib.mkForce false;

    systemd.services.sinex-dev-cache-prune = {
      restartIfChanged = false;
      serviceConfig = maintenanceServiceConfig "sinex-dev-cache-prune.service";
    };

    # Allow realtime priority for audio
    security.pam.loginLimits = [
      {
        domain = "@users";
        type = "-";
        item = "rtprio";
        value = "99";
      }
      {
        domain = "@users";
        type = "-";
        item = "nice";
        value = "-15";
      }
    ];
  };
}
