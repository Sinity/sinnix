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
      # Default 10 is too aggressive - system fights to keep everything in RAM
      # until hitting wall, then thrashes. 60 = proactive cold page eviction.
      boot.kernel.sysctl = {
        "vm.swappiness" = 60;
        "vm.vfs_cache_pressure" = 50; # Keep inode/dentry caches longer
        "vm.dirty_ratio" = 10; # Start writebacks earlier (default 20)
        "vm.dirty_background_ratio" = 5; # Background writeback threshold
      };

      # zram: compressed RAM swap - faster than SSD, effectively extends RAM
      # Compression ratio ~2-3x for typical workloads (debug symbols compress well)
      zramSwap = {
        enable = true;
        algorithm = "zstd"; # Best compression/speed tradeoff
        memoryPercent = 50; # Use up to 50% of RAM as compressed swap
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
          {
            type = "Heavy_Build";
            nice = 15;
            sched = "batch";
            ioclass = "idle";
            oom_score_adj = 300;
          }
          {
            type = "Light_Build";
            nice = 10;
            sched = "batch";
            ioclass = "idle";
            oom_score_adj = 200;
          }
          {
            type = "Critical_Interactive";
            nice = -15;
            ioclass = "best-effort";
            ioprio = 0;
            oom_score_adj = -800;
          }
        ];

        extraRules = [
          # Build tools (compilers, linkers) - heavy background processing
          {
            name = "gcc";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "g++";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "clang";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "clang++";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "rustc";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "cc1";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "cc1plus";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "ld";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "lld";
            type = "Heavy_Build";
            cgroup = "build";
          }
          {
            name = "mold";
            type = "Heavy_Build";
            cgroup = "build";
          }

          # Build system coordinators - lighter weight
          {
            name = "cargo";
            type = "Light_Build";
            cgroup = "build";
          }
          {
            name = "cmake";
            type = "Light_Build";
            cgroup = "build";
          }
          {
            name = "make";
            type = "Light_Build";
            cgroup = "build";
          }
          {
            name = "ninja";
            type = "Light_Build";
            cgroup = "build";
          }
          {
            name = "meson";
            type = "Light_Build";
            cgroup = "build";
          }

          # Compression/decompression - background
          {
            name = "xz";
            type = "BG_CPUIO";
            nice = 15;
            ioclass = "idle";
          }
          {
            name = "gzip";
            type = "BG_CPUIO";
            nice = 15;
            ioclass = "idle";
          }
          {
            name = "bzip2";
            type = "BG_CPUIO";
            nice = 15;
            ioclass = "idle";
          }
          {
            name = "zstd";
            type = "BG_CPUIO";
            nice = 15;
            ioclass = "idle";
          }

          # Indexing and file search - background
          {
            name = "updatedb";
            type = "BG_CPUIO";
            nice = 19;
            ioclass = "idle";
          }
          {
            name = "locate";
            type = "BG_CPUIO";
            nice = 10;
            ioclass = "idle";
          }

          # Compositor - critical real-time priority
          {
            name = "Hyprland";
            type = "LowLatency_RT";
            nice = -10;
            ioclass = "realtime";
            ioprio = 0;
            oom_score_adj = -100;
          }
          {
            name = ".Hyprland-wrapped";
            type = "LowLatency_RT";
            nice = -10;
            ioclass = "realtime";
            ioprio = 0;
            oom_score_adj = -100;
          }

          # Terminal emulators - high priority for responsiveness
          {
            name = "kitty";
            type = "LowLatency_RT";
            nice = -5;
            ioclass = "best-effort";
            ioprio = 0;
            oom_score_adj = -50;
          }
          {
            name = "alacritty";
            type = "LowLatency_RT";
            nice = -5;
            ioclass = "best-effort";
            ioprio = 0;
            oom_score_adj = -50;
          }

          # Input interception pipeline - keep input responsive under load
          {
            name = "intercept";
            type = "Critical_Interactive";
          }
          {
            name = "interception-tools";
            type = "Critical_Interactive";
          }
          {
            name = "intercept-bounce";
            type = "Critical_Interactive";
          }
          {
            name = "scribe-tap";
            type = "Critical_Interactive";
          }
          {
            name = "caps2esc";
            type = "Critical_Interactive";
          }
          {
            name = "uinput";
            type = "Critical_Interactive";
          }
          {
            name = "systemd-logind";
            type = "Critical_Interactive";
          }
          {
            name = "systemd-udevd";
            type = "Critical_Interactive";
          }

          # SSH and TTY login paths - keep recovery access snappy under load
          {
            name = "sshd";
            type = "Critical_Interactive";
          }
          {
            name = "sshd-session";
            type = "Critical_Interactive";
          }
          {
            name = "ssh";
            type = "Critical_Interactive";
          }
          {
            name = "sftp-server";
            type = "Critical_Interactive";
          }
          {
            name = "agetty";
            type = "Critical_Interactive";
          }
          {
            name = "login";
            type = "Critical_Interactive";
          }
          {
            name = "bash";
            type = "Critical_Interactive";
          }
          {
            name = "zsh";
            type = "Critical_Interactive";
          }

          # System daemons - protected
          {
            name = "systemd";
            oom_score_adj = -1000;
          }
          {
            name = "dbus-broker";
            oom_score_adj = -900;
          }
          {
            name = "pipewire";
            type = "LowLatency_RT";
            nice = -11;
            oom_score_adj = -100;
          }
          {
            name = "wireplumber";
            type = "LowLatency_RT";
            nice = -11;
            oom_score_adj = -100;
          }

          # Browsers - normal priority but killable under OOM
          {
            name = "chromium";
            type = "Player";
            nice = 0;
            ioclass = "best-effort";
            ioprio = 2;
            oom_score_adj = 200;
          }
          {
            name = "firefox";
            type = "Player";
            nice = 0;
            ioclass = "best-effort";
            ioprio = 2;
            oom_score_adj = 200;
          }

          # Media players - normal with smooth playback
          {
            name = "mpv";
            type = "Player";
            nice = -5;
            ioclass = "best-effort";
            ioprio = 1;
          }
          {
            name = "vlc";
            type = "Player";
            nice = -5;
            ioclass = "best-effort";
            ioprio = 1;
          }
        ];

        extraCgroups = [
          {
            cgroup = "build";
            CPUWeight = 30;
            IOWeight = 30;
            MemoryHigh = "16G";
            MemoryMax = "20G";
          }
        ];
      };

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
    })
  ];
}
