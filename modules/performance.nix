# Performance Tuning
#
# Philosophy: under memory pressure, KILL fast — do not thrash. zram and
# systemd-oomd both delayed kills until the desktop was already wedged
# (zram thrashes compression cycles instead of freeing real RAM; oomd PSI
# accounting needs ~15s of sustained pressure before it acts). Replaced with
# earlyoom, which polls /proc/meminfo every 100ms and SIGKILLs the largest
# offender in well under a second. A small disk swapfile (declared in the
# host storage module) stays as a release valve for genuinely cold pages.
{
  pkgs,
  lib,
  config,
  ...
}:
let
  resourceBudgets = import ./lib/resource-budgets.nix;
  buildBudget = resourceBudgets.developerWork.sliceConfig;
  graphicalBudget = resourceBudgets.graphical.sliceConfig;
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
      script = ''
        panic_dir="/realm/data/captures/syslog/panic"
        if [ -d /sys/fs/pstore ] && [ "$(ls -A /sys/fs/pstore 2>/dev/null)" ]; then
          install -d -m 0755 "$panic_dir"
          dest="$panic_dir/panic-$(date +%Y%m%dT%H%M%S)"
          mkdir -p "$dest"
          cp -r /sys/fs/pstore/* "$dest/"
          chmod -R 0644 "$dest"/*
          echo "Captured $(ls /sys/fs/pstore | wc -l) pstore entries to $dest"
          # Clean pstore to free the reserved RAM region for next panic
          for f in /sys/fs/pstore/*; do
            : > "$f" 2>/dev/null || true
          done
        fi
      '';
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
        "^(systemd|systemd-.*|Hyprland|sway|gnome-shell|kwin|Xorg|sshd|kitty|foot|bash|zsh|tmux)$"
        # Prefer to kill big memory hogs that we can always restart.
        "--prefer"
        "^(electron|chrome|chromium|firefox|node|cargo|rustc|ld|ld\\.lld|ld\\.mold|cc1|cc1plus|nix|nix-build|cmake|ninja|monado|wivrn|waybar|claude|codex|gemini|forge|nats-server|tofi)$"
      ];
    };

    # systemd-oomd is disabled: its 15s PSI accumulation window means the
    # box can wedge before it ever fires. earlyoom replaces it.
    systemd.oomd.enable = false;

    # Keep a small floor for the logged-in user, but do not make the entire
    # user session an unlimited preferred survivor. Terminals, AI agents,
    # browsers, and ad-hoc dev stacks all live under user.slice; protecting the
    # whole parent made the desktop swap-thrash instead of killing the runaway
    # child cgroup.
    #
    # MemoryMax provides a hard ceiling so a single runaway process inside the
    # session cannot push the whole system into swap-thrash territory.
    # TasksMax prevents PID-space exhaustion: a thread-exploding build or fork
    # bomb inside user.slice leaves enough PIDs for recovery shells.
    systemd.slices.user.sliceConfig = {
      CPUWeight = 1000;
      IOWeight = 1000;
      MemoryLow = "4G";
      MemoryHigh = "20G"; # soft reclaim trigger, well below the 24G hard ceiling
      MemoryMax = "24G";
      TasksMax = "10000";
    };

    # User-manager background/graphical slices need their own budgets. Do not
    # cap Kitty's aggregate slice: one throttled `memory.high` bucket stalls all
    # terminals, including the interactive shell needed to recover the machine.
    # Heavy terminal-launched work must be moved into `build.slice` or
    # `background.slice` instead of punishing the whole terminal surface.
    systemd.user.slices = {
      background.sliceConfig = buildBudget;

      # Graphical apps can be large, especially browsers, but they should not be
      # able to consume all RAM plus zram before oomd reacts.
      app.sliceConfig = graphicalBudget;

      # Preserve the compositor/session supervisor paths preferentially.
      session.sliceConfig = {
        ManagedOOMPreference = "avoid";
        MemoryLow = "1G";
        CPUWeight = 1000;
        IOWeight = 1000;
      };

      # Interactive build/test entrypoints enter this slice through
      # Sinnix-owned wrappers such as `sinnix-scope` and `pytest`. Rust
      # project-specific orchestration should prefer repo control planes
      # such as Sinex `xtask`, not a global transparent cargo wrapper.
      build.sliceConfig = buildBudget // {
        IOWriteBandwidthMax = [
          "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 300M" # /realm NVMe
          "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 300M" # /cache NVMe
        ];
      };
    };

    # Put Nix builds in an explicitly budgeted slice so they cannot consume the
    # entire workstation even when individual derivations fan out internally.
    # IOWriteBandwidthMax provides a hard ceiling so bulk writes from large
    # builds (Rust target/ trees, linker output) cannot saturate the NVMe and
    # starve interactive I/O paths (terminals, browsers, desktop compositor).
    systemd.slices."nix-build" = {
      description = "Resource budget for Nix builds";
      sliceConfig = buildBudget // {
        IOWriteBandwidthMax = [
          "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 300M"
          "/dev/disk/by-uuid/7f603111-8f3a-40aa-bad0-0cac69c140f1 300M"
        ];
      };
    };

    # Generic background scopes should inherit the same low-priority budget as
    # Nix builds so wrappers like `nix-safe` and future backgrounded dev tasks
    # do not run at full desktop priority by accident.
    systemd.slices.background = {
      description = "Resource budget for background developer work";
      sliceConfig = buildBudget;
    };

    # The slices above are the source of truth. Helper wrappers should target
    # the correct slice instead of re-stating the whole resource envelope.
    systemd.services.nix-daemon.serviceConfig = {
      Slice = "nix-build.slice";
    }
    // buildBudget;

    # home-manager-${user}.service is the actual file-linker; it is pulled in
    # by switch-to-configuration but runs as its own system unit, so the parent
    # slice does not propagate. Do not define
    # nixos-rebuild-switch-to-configuration.service here: nixos-rebuild-ng
    # creates that name as a transient unit, and any static fragment makes
    # systemd-run refuse the activation job.
    systemd.services."home-manager-${config.sinnix.user.name}".serviceConfig.Slice = "nix-build.slice";

    # Ananicy: per-process nice/ioclass for desktop responsiveness
    services.ananicy = {
      enable = true;
      package = pkgs.ananicy-cpp;
      rulesProvider = pkgs.ananicy-rules-cachyos;
      settings = {
        apply_oom_score_adj = true;
        # ananicy-cpp cgroup placement is erroring on this host
        # (Invalid argument on /sys/fs/cgroup/cgroup.procs).
        # Keep priority/ionice/scheduler tuning, disable cgroup writes.
        cgroup_load = false;
        apply_cgroup = false;
      };

      extraTypes = [
        {
          type = "Heavy_Build";
          nice = 15;
          sched = "batch";
          ioclass = "idle";
        }
        {
          type = "Light_Build";
          nice = 10;
          sched = "batch";
          ioclass = "idle";
        }
      ];

      extraRules = [
        # Compilers/linkers
        {
          name = "gcc";
          type = "Heavy_Build";
        }
        {
          name = "cc";
          type = "Heavy_Build";
        }
        {
          name = "g++";
          type = "Heavy_Build";
        }
        {
          name = "c++";
          type = "Heavy_Build";
        }
        {
          name = "clang";
          type = "Heavy_Build";
        }
        {
          name = "clang++";
          type = "Heavy_Build";
        }
        {
          name = "rustc";
          type = "Heavy_Build";
        }
        {
          name = "cc1";
          type = "Heavy_Build";
        }
        {
          name = "cc1plus";
          type = "Heavy_Build";
        }
        {
          name = "ld";
          type = "Heavy_Build";
        }
        {
          name = "lld";
          type = "Heavy_Build";
        }
        {
          name = "ld.lld";
          type = "Heavy_Build";
        }
        {
          name = "ld.gold";
          type = "Heavy_Build";
        }
        {
          name = "mold";
          type = "Heavy_Build";
        }
        {
          name = "ld.mold";
          type = "Heavy_Build";
        }
        {
          name = "cargo";
          type = "Light_Build";
        }
        {
          name = "nix";
          type = "Heavy_Build";
        }

        # LSPs and language servers
        {
          name = "rust-analyzer";
          type = "Heavy_Build";
        }
        {
          name = "pyrefly";
          type = "Heavy_Build";
        }
        {
          name = "nil";
          type = "Light_Build";
        }
        {
          name = "nixd";
          type = "Light_Build";
        }
        {
          name = "typescript-language-server";
          type = "Light_Build";
        }
        {
          name = "gopls";
          type = "Light_Build";
        }
        {
          name = "cargo-nextest";
          type = "Light_Build";
        }
        {
          name = "ninja";
          type = "Heavy_Build";
        }
        {
          name = "cmake";
          type = "Light_Build";
        }
        {
          name = "meson";
          type = "Light_Build";
        }
        {
          name = "make";
          type = "Heavy_Build";
        }
        {
          name = "ctest";
          type = "Heavy_Build";
        }
        {
          name = "pytest";
          type = "Heavy_Build";
        }
        {
          name = "qemu-system-x86_64";
          type = "Heavy_Build";
        }
        {
          name = "qemu-kvm";
          type = "Heavy_Build";
        }
      ];
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
