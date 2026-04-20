# Performance Tuning
#
# Philosophy: keep the desktop responsive under pressure by giving the kernel a
# meaningful zram-backed landing zone for bursts, then containing runaway work
# in dedicated slices before the whole box degrades.
{
  pkgs,
  lib,
  config,
  ...
}:
let
  buildBudget = {
    MemoryHigh = "18G";
    MemoryMax = "20G";
    MemorySwapMax = "0";
    ManagedOOMMemoryPressure = "kill";
    ManagedOOMMemoryPressureLimit = "50%";
    CPUWeight = 5;
    IOWeight = 5;
  };
in
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    # Give the kernel a modest compressed buffer for burst absorption. The goal
    # is not to run the workstation out of swap; it is to avoid instant hard
    # failure on short spikes while keeping steady-state pressure out of swap.
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      memoryPercent = 20;
    };

    systemd.settings.Manager = {
      StatusUnitFormat = "name";
    };

    boot.kernel.sysctl = {
      # Allow some zram use during transient pressure without turning the normal
      # desktop path into a swap-first policy.
      "vm.swappiness" = 40;
      # zram is cheap random access; clustered swap readahead just adds latency.
      "vm.page-cluster" = 0;
      # Keep inode/dentry cache hot — NixOS store paths are long and frequently
      # resolved. Reducing eviction pressure improves terminal startup latency.
      "vm.vfs_cache_pressure" = 50;
      # Flush dirty pages earlier to avoid bursty I/O spikes.
      "vm.dirty_background_ratio" = 5;
      "vm.dirty_ratio" = 10;
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

    # Use cgroup-aware OOM policy so runaway build/test work is killed inside
    # its own slice instead of forcing whole-system contention decisions.
    services.earlyoom.enable = false;

    systemd.oomd = {
      enable = true;
      enableSystemSlice = true;
      enableUserSlices = true;
      settings.OOM.DefaultMemoryPressureDurationSec = "15s";
    };

    # Keep the actual interactive user slice as the preferred survivor under
    # pressure. `user.slice` is the live cgroup that holds session scopes; the
    # old wildcard-style `user-` unit did not protect the host in practice.
    systemd.slices.user.sliceConfig = {
      CPUWeight = 1000;
      IOWeight = 1000;
      ManagedOOMPreference = "avoid";
      MemoryLow = "10G";
    };

    # Put Nix builds in an explicitly budgeted slice so they cannot consume the
    # entire workstation even when individual derivations fan out internally.
    systemd.slices."nix-build" = {
      description = "Resource budget for Nix builds";
      sliceConfig = buildBudget;
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
    } // buildBudget;

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
