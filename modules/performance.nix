{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.machine;
in
{
  config = lib.mkMerge [
    # Memory tuning - always applied
    {
      boot.kernel.sysctl = {
        "vm.swappiness" = 15; # Low for zram - prefer oomd over thrashing
        "vm.vfs_cache_pressure" = 50;
        "vm.dirty_ratio" = 10;
        "vm.dirty_background_ratio" = 5;
      };

      zramSwap = {
        enable = true;
        algorithm = "zstd";
        memoryPercent = 10;
        priority = 100;
      };

      # Use systemd-oomd (enabled by default in NixOS) with cgroup memory limits
      systemd.oomd.enableUserSlices = true;

      systemd.services = lib.mkMerge [
        {
          nix-daemon.serviceConfig.Slice = "builds-nix\\x2ddaemon.slice";

          # Recovery services (protected from oomd)
          "systemd-logind".serviceConfig.Slice = "recovery.slice";
          "systemd-udevd".serviceConfig.Slice = "recovery.slice";
          "systemd-journald".serviceConfig.Slice = "recovery.slice";
        }
        (lib.genAttrs
          [ "getty@tty1" "getty@tty2" "getty@tty3" "getty@tty4" "getty@tty5" "getty@tty6" ]
          (_: { serviceConfig.Slice = "recovery.slice"; }))
      ];

      systemd.slices = {
        "builds".sliceConfig = {
          MemoryHigh = "28G";
          MemoryMax = "30G";
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "95%";
        };

        "builds-nix\\x2ddaemon".sliceConfig = {
          CPUWeight = 40;
          IOWeight = 40;
          MemoryHigh = "18G"; # Reduced to avoid contention with user slice
          MemoryMax = "22G";
        };

        "user".sliceConfig = {
          CPUWeight = 500;
          IOWeight = 500;
          MemoryHigh = "22G"; # Leave ~10G for kernel + builds + recovery
          MemoryMax = "24G";
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "80%"; # Trigger earlier for graceful degradation
        };

        "recovery".sliceConfig = {
          CPUWeight = 1000;
          IOWeight = 1000;
          ManagedOOMMemoryPressure = "none";
          MemoryLow = "2G"; # Proper headroom for journald, udevd, logind, getty
        };
      };
    }

    # Desktop-specific performance tuning
    (lib.mkIf cfg.isDesktop {
      services.ananicy = {
        enable = true;
        package = pkgs.ananicy-cpp;
        rulesProvider = pkgs.ananicy-rules-cachyos;
        settings.apply_oom_score_adj = true;
        extraTypes = [
          { type = "Heavy_Build"; nice = 15; sched = "batch"; ioclass = "idle"; oom_score_adj = 300; }
          { type = "Light_Build"; nice = 10; sched = "batch"; ioclass = "idle"; oom_score_adj = 200; }
        ];
        # Only rules not in cachyos defaults
        extraRules = [
          # Compilers/linkers (not in cachyos)
          { name = "gcc"; type = "Heavy_Build"; }
          { name = "g++"; type = "Heavy_Build"; }
          { name = "clang"; type = "Heavy_Build"; }
          { name = "clang++"; type = "Heavy_Build"; }
          { name = "rustc"; type = "Heavy_Build"; }
          { name = "cc1"; type = "Heavy_Build"; }
          { name = "cc1plus"; type = "Heavy_Build"; }
          { name = "ld"; type = "Heavy_Build"; }
          { name = "lld"; type = "Heavy_Build"; }
          { name = "mold"; type = "Heavy_Build"; }
          { name = "cargo"; type = "Light_Build"; }
          { name = "nix"; type = "Heavy_Build"; }

          # Input pipeline (custom, not in cachyos)
          { name = "intercept"; oom_score_adj = -800; }
          { name = "intercept-bounce"; oom_score_adj = -800; }
          { name = "scribe-tap"; oom_score_adj = -800; }

          # Browsers: high oom_score so oomd kills these first
          { name = "chromium"; oom_score_adj = 300; }
          { name = "chrome"; oom_score_adj = 300; }
          { name = "firefox"; oom_score_adj = 300; }
          { name = "steam"; oom_score_adj = 300; }
        ];
      };

      security.pam.loginLimits = [
        { domain = "@users"; type = "-"; item = "rtprio"; value = "99"; }
        { domain = "@users"; type = "-"; item = "nice"; value = "-15"; }
      ];

      # Allow user to create scopes in builds.slice without sudo
      security.polkit.extraConfig = ''
        polkit.addRule(function(action, subject) {
          if (action.id == "org.freedesktop.systemd1.manage-units" &&
              subject.user == "${config.sinnix.user.name}" &&
              subject.local && subject.active) {
            var unit = action.lookup("unit");
            if (unit && (unit.indexOf("builds.slice") !== -1 || unit.startsWith("run-"))) {
              return polkit.Result.YES;
            }
          }
        });
      '';
    })

    # Build parallelism - full speed, memory controlled by cgroup wrapper
    {
      environment.variables = {
        CARGO_BUILD_JOBS = "8";
        CARGO_PROFILE_DEV_CODEGEN_UNITS = "16";
        CARGO_PROFILE_RELEASE_CODEGEN_UNITS = "1";
      };
    }
  ];
}
