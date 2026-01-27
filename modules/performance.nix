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
    # Memory tuning - always applied (not just desktop)
    {
      # Prevent swap thrashing during heavy compilation
      boot.kernel.sysctl = {
        "vm.swappiness" = 60;
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

      systemd.oomd = {
        enable = true;
        enableRootSlice = true;
        enableUserSlices = true;
        enableSystemSlice = true;
        settings.OOM = {
          DefaultMemoryPressureDurationSec = "20s";
        };
      };

      systemd.services = lib.mkMerge [
        {
          nix-daemon.serviceConfig = {
            MemoryHigh = "24G";
            MemoryMax = "28G";
            OOMScoreAdjust = 250;
            Slice = "nix-daemon.slice";
          };
          "systemd-logind".serviceConfig.Slice = "recovery.slice";
          "systemd-udevd".serviceConfig.Slice = "recovery.slice";
          "systemd-journald".serviceConfig.Slice = "recovery.slice";
        }
        (lib.genAttrs
          [ "getty@tty1" "getty@tty2" "getty@tty3" "getty@tty4" "getty@tty5" "getty@tty6" ]
          (_: { serviceConfig.Slice = "recovery.slice"; }))
      ];

      systemd.slices = {
        "nix-daemon.slice".sliceConfig = {
          Description = "Resource limits for nix-daemon builds";
          CPUWeight = 40;
          IOWeight = 40;
          MemoryHigh = "20G";
          MemoryMax = "24G";
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "95%";
        };

        "user.slice".sliceConfig = {
          Description = "High priority for user session (UI, terminals)";
          CPUWeight = 500;
          IOWeight = 500;
          ManagedOOMMemoryPressure = "kill";
          ManagedOOMMemoryPressureLimit = "90%";
        };

        "recovery.slice".sliceConfig = {
          Description = "High priority recovery services (SSH, TTY)";
          CPUWeight = 1000;
          IOWeight = 1000;
          ManagedOOMMemoryPressure = "none";
          MemoryLow = "512M";
        };
      };

      services.earlyoom = {
        enable = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 10;
        enableNotifications = true;
        extraArgs = [
          "--prefer" "^(cc1|cc1plus|rustc|clang|ld|lld|nix-build|nix-daemon)$"
          "--avoid" "^(Hyprland|pipewire|wireplumber|kitty|systemd)$"
          "-r" "60"
        ];
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
          { name = "gcc"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "g++"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "clang"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "clang++"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "rustc"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "cc1"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "cc1plus"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "ld"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "lld"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "mold"; type = "Heavy_Build"; cgroup = "build"; }
          { name = "cargo"; type = "Light_Build"; cgroup = "build"; }
          { name = "cmake"; type = "Light_Build"; cgroup = "build"; }
          { name = "make"; type = "Light_Build"; cgroup = "build"; }
          { name = "ninja"; type = "Light_Build"; cgroup = "build"; }
          { name = "meson"; type = "Light_Build"; cgroup = "build"; }
          { name = "xz"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "gzip"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "bzip2"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "zstd"; type = "BG_CPUIO"; nice = 15; ioclass = "idle"; }
          { name = "updatedb"; type = "BG_CPUIO"; nice = 19; ioclass = "idle"; }
          { name = "locate"; type = "BG_CPUIO"; nice = 10; ioclass = "idle"; }
          { name = "Hyprland"; type = "LowLatency_RT"; nice = -10; ioclass = "realtime"; ioprio = 0; oom_score_adj = -100; }
          { name = ".Hyprland-wrapped"; type = "LowLatency_RT"; nice = -10; ioclass = "realtime"; ioprio = 0; oom_score_adj = -100; }
          { name = "kitty"; type = "LowLatency_RT"; nice = -5; ioclass = "best-effort"; ioprio = 0; oom_score_adj = -50; }
          { name = "alacritty"; type = "LowLatency_RT"; nice = -5; ioclass = "best-effort"; ioprio = 0; oom_score_adj = -50; }
          { name = "intercept"; type = "Critical_Interactive"; }
          { name = "interception-tools"; type = "Critical_Interactive"; }
          { name = "intercept-bounce"; type = "Critical_Interactive"; }
          { name = "scribe-tap"; type = "Critical_Interactive"; }
          { name = "caps2esc"; type = "Critical_Interactive"; }
          { name = "uinput"; type = "Critical_Interactive"; }
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
          { name = "systemd"; oom_score_adj = -1000; }
          { name = "dbus-broker"; oom_score_adj = -900; }
          { name = "pipewire"; type = "LowLatency_RT"; nice = -11; oom_score_adj = -100; }
          { name = "wireplumber"; type = "LowLatency_RT"; nice = -11; oom_score_adj = -100; }
          { name = "chromium"; type = "Player"; nice = 0; ioclass = "best-effort"; ioprio = 2; oom_score_adj = 200; }
          { name = "firefox"; type = "Player"; nice = 0; ioclass = "best-effort"; ioprio = 2; oom_score_adj = 200; }
          { name = "mpv"; type = "Player"; nice = -5; ioclass = "best-effort"; ioprio = 1; }
          { name = "vlc"; type = "Player"; nice = -5; ioclass = "best-effort"; ioprio = 1; }
        ];
        extraCgroups = [ { cgroup = "build"; CPUWeight = 30; IOWeight = 30; MemoryHigh = "14G"; MemoryMax = "16G"; } ];
      };

      security.pam.loginLimits = [
        { domain = "@users"; type = "-"; item = "rtprio"; value = "99"; }
        { domain = "@users"; type = "-"; item = "nice"; value = "-15"; }
      ];

      systemd.user.slices.build = {
        description = "Build processes slice with memory limits";
        sliceConfig = {
          MemoryHigh = "14G";
          MemoryMax = "16G";
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
