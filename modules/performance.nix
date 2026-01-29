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
        # Low swappiness for zram-only system (prefer earlyoom trigger over aggressive swap)
        "vm.swappiness" = 15;
        "vm.vfs_cache_pressure" = 50;
        "vm.dirty_ratio" = 10;
        "vm.dirty_background_ratio" = 5;
      };

      zramSwap = {
        enable = true;
        algorithm = "zstd";
        memoryPercent = 10; # 3.2GB → ~9-12GB effective with zstd compression
        priority = 100;
      };

      # Single OOM killer: earlyoom (has tuned prefer/avoid lists)
      # systemd-oomd removed - dual killers race and cause conflicts
      services.earlyoom = {
        enable = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 10;
        enableNotifications = true;
        extraArgs = [
          "--prefer" "^(nix|nix-daemon|cc1|cc1plus|rustc|clang|ld|lld)$"
          "--avoid" "^(Hyprland|pipewire|wireplumber|kitty|systemd)$"
          "-r" "60"
        ];
      };

      systemd.services = lib.mkMerge [
        {
          # nix-daemon in builds-nix-daemon.slice (child of builds.slice)
          nix-daemon.serviceConfig = {
            OOMScoreAdjust = 300; # Match Heavy_Build (kill first)
            Slice = "builds-nix\\x2ddaemon.slice";
          };

          # Recovery services (never killed)
          "systemd-logind".serviceConfig.Slice = "recovery.slice";
          "systemd-udevd".serviceConfig.Slice = "recovery.slice";
          "systemd-journald".serviceConfig.Slice = "recovery.slice";
        }
        (lib.genAttrs
          [ "getty@tty1" "getty@tty2" "getty@tty3" "getty@tty4" "getty@tty5" "getty@tty6" ]
          (_: { serviceConfig.Slice = "recovery.slice"; }))
      ];

      systemd.slices = {
        # Parent slice: caps TOTAL build memory if both active simultaneously
        "builds.slice".sliceConfig = {
          Description = "All build processes (nix-daemon + user)";
          MemoryHigh = "28G";
          MemoryMax = "30G";
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "95%";
        };

        # nix-daemon child slice (under builds.slice)
        "builds-nix\\x2ddaemon.slice".sliceConfig = {
          Description = "Nix daemon builds";
          CPUWeight = 40;
          IOWeight = 40;
          MemoryHigh = "24G";
          MemoryMax = "28G";
        };

        # User slice (high priority for UI)
        "user.slice".sliceConfig = {
          Description = "High priority user session (UI, terminals)";
          CPUWeight = 500;
          IOWeight = 500;
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "90%";
        };

        # Recovery slice (SSH, TTYs - never killed)
        "recovery.slice".sliceConfig = {
          Description = "Recovery services (SSH, TTY, logging)";
          CPUWeight = 1000;
          IOWeight = 1000;
          ManagedOOMMemoryPressure = "none";
          MemoryLow = "512M";
        };
      };
    }

    # Desktop-specific performance tuning
    (lib.mkIf cfg.isDesktop {
      services.ananicy = {
        enable = true;
        package = pkgs.ananicy-cpp;
        rulesProvider = pkgs.ananicy-rules-cachyos;
        settings = {
          cgroup_realtime_workaround = true;
          apply_oom_score_adj = true;
        };
        extraTypes = [
          { type = "Heavy_Build"; nice = 15; sched = "batch"; ioclass = "idle"; oom_score_adj = 300; }
          { type = "Light_Build"; nice = 10; sched = "batch"; ioclass = "idle"; oom_score_adj = 200; }
          { type = "Critical_Interactive"; nice = -15; ioclass = "best-effort"; ioprio = 0; oom_score_adj = -800; }
        ];
        extraRules = [
          # Build tools → build cgroup (user.slice descendant)
          { name = "gcc"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "g++"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "clang"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "clang++"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "rustc"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "cc1"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "cc1plus"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "ld"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "lld"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "mold"; type = "Heavy_Build"; cgroup = "user/build"; }
          { name = "cargo"; type = "Light_Build"; cgroup = "user/build"; }
          { name = "cmake"; type = "Light_Build"; cgroup = "user/build"; }
          { name = "make"; type = "Light_Build"; cgroup = "user/build"; }
          { name = "ninja"; type = "Light_Build"; cgroup = "user/build"; }
          { name = "meson"; type = "Light_Build"; cgroup = "user/build"; }

          # nix CLI also heavy build (nix eval can eat 20GB+)
          { name = "nix"; type = "Heavy_Build"; cgroup = "user/build"; }

          # nix-daemon separate (handled by slice config)
          { name = "nix-daemon"; oom_score_adj = 300; }

          # Background compression
          { name = "xz"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "gzip"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "bzip2"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "zstd"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "updatedb"; type = "BG_CPUIO"; nice = 19; ioclass = "idle"; }
          { name = "locate"; type = "BG_CPUIO"; nice = 10; ioclass = "idle"; }

          # WM + terminals (low latency, protect from OOM)
          { name = "Hyprland"; type = "LowLatency_RT"; nice = -10; ioclass = "realtime"; ioprio = 0; oom_score_adj = -100; }
          { name = ".Hyprland-wrapped"; type = "LowLatency_RT"; nice = -10; ioclass = "realtime"; ioprio = 0; oom_score_adj = -100; }
          { name = "kitty"; type = "LowLatency_RT"; nice = -5; ioclass = "best-effort"; ioprio = 0; oom_score_adj = -50; }
          { name = "alacritty"; type = "LowLatency_RT"; nice = -5; ioclass = "best-effort"; ioprio = 0; oom_score_adj = -50; }

          # Input/keyboard critical (never kill)
          { name = "intercept"; type = "Critical_Interactive"; }
          { name = "interception-tools"; type = "Critical_Interactive"; }
          { name = "intercept-bounce"; type = "Critical_Interactive"; }
          { name = "scribe-tap"; type = "Critical_Interactive"; }
          { name = "caps2esc"; type = "Critical_Interactive"; }
          { name = "uinput"; type = "Critical_Interactive"; }

          # System services (never kill)
          { name = "systemd-logind"; type = "Critical_Interactive"; }
          { name = "systemd-udevd"; type = "Critical_Interactive"; }
          { name = "sshd"; type = "Critical_Interactive"; }
          { name = "sshd-session"; type = "Critical_Interactive"; }
          { name = "ssh"; type = "Critical_Interactive"; }
          { name = "sftp-server"; type = "Critical_Interactive"; }
          { name = "agetty"; type = "Critical_Interactive"; }
          { name = "login"; type = "Critical_Interactive"; }
          { name = "bash"; type = "Critical_Interactive"; }
          { name = "zsh"; type = "Critical_Interactive"; }

          # Core daemons (highest protection)
          { name = "systemd"; oom_score_adj = -1000; }
          { name = "dbus-broker"; oom_score_adj = -900; }
          { name = "pipewire"; type = "LowLatency_RT"; nice = -11; oom_score_adj = -100; }
          { name = "wireplumber"; type = "LowLatency_RT"; nice = -11; oom_score_adj = -100; }

          # Browsers/media (acceptable to kill)
          { name = "chromium"; type = "Player"; nice = 0; ioclass = "best-effort"; ioprio = 2; oom_score_adj = 200; }
          { name = "firefox"; type = "Player"; nice = 0; ioclass = "best-effort"; ioprio = 2; oom_score_adj = 200; }
          { name = "mpv"; type = "Player"; nice = -5; ioclass = "best-effort"; ioprio = 1; }
          { name = "vlc"; type = "Player"; nice = -5; ioclass = "best-effort"; ioprio = 1; }
        ];

        # User build cgroup (child of user.slice)
        extraCgroups = [
          { cgroup = "user/build"; CPUWeight = 30; IOWeight = 30; MemoryHigh = "24G"; MemoryMax = "28G"; }
        ];
      };

      security.pam.loginLimits = [
        { domain = "@users"; type = "-"; item = "rtprio"; value = "99"; }
        { domain = "@users"; type = "-"; item = "nice"; value = "-15"; }
      ];

      systemd.user.slices.build = {
        description = "User build processes (cargo, make, cmake)";
        sliceConfig = {
          MemoryHigh = "24G";
          MemoryMax = "28G";
          CPUWeight = 30;
          IOWeight = 30;
        };
      };
    })

    # Build parallelism
    {
      environment.variables = {
        CARGO_BUILD_JOBS = "8";
        CARGO_PROFILE_DEV_CODEGEN_UNITS = "16";
        CARGO_PROFILE_RELEASE_CODEGEN_UNITS = "1";
      };
    }
  ];
}
