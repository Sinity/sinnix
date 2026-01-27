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

      # zram: small compressed swap buffer - gives earlyoom time to act
      # NOT for extending RAM capacity (that silently kills performance)
      # 10% of 32GB = 3.2GB capacity → just a safety buffer before OOM killer
      zramSwap = {
        enable = true;
        algorithm = "zstd"; # Best compression/speed tradeoff
        memoryPercent = 10; # Minimal: buffer for earlyoom, not RAM extension
        priority = 100; # High priority: prefer zram over disk swap
      };

      # earlyoom: kill memory hogs BEFORE system thrashes
      # Acts on memory+swap pressure, not just when OOM is imminent
      services.earlyoom = {
        enable = true;
        freeMemThreshold = 5; # Act when <5% RAM free
        freeSwapThreshold = 10; # Act when <10% swap free (catches zram filling)
        enableNotifications = true;

        # Prefer killing build processes over interactive apps
        extraArgs = [
          "--prefer" "^(cc1|cc1plus|rustc|clang|ld|lld|nix-build|nix-daemon)$"
          "--avoid" "^(Hyprland|pipewire|wireplumber|kitty|systemd)$"
          "-r" "60" # Check every 60 seconds (default 1s is too aggressive)
        ];
      };

      # systemd-oomd: complementary to earlyoom, uses PSI (pressure stall info)
      systemd.oomd = {
        enable = true;
        enableRootSlice = true;
        enableUserSlices = true;
        enableSystemSlice = true;
        settings.OOM = {
          # Kill when memory pressure sustained >20 seconds
          DefaultMemoryPressureDurationSec = "20s";
        };
      };

      # nix-daemon memory limits: prevent nix builds from consuming all RAM
      # This is the key fix for "cargo build + nix build = thrash"
      systemd.services.nix-daemon.serviceConfig = {
        # MemoryHigh: soft limit - kernel will reclaim aggressively above this
        MemoryHigh = "24G";
        # MemoryMax: hard limit - OOM kill nix workers if exceeded
        MemoryMax = "28G";
        # Make nix-daemon children killable before system-critical services
        OOMScoreAdjust = 250;
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
            MemoryHigh = "14G";
            MemoryMax = "16G";
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

      # Systemd slice for builds - these limits ACTUALLY work unlike ananicy extraCgroups
      # Use with: systemd-run --user --slice=build.slice cargo build
      # Limits match CARGO_BUILD_JOBS expectation: 8 jobs × 2GB = 16GB max
      systemd.user.slices.build = {
        description = "Build processes slice with memory limits";
        sliceConfig = {
          MemoryHigh = "14G"; # Soft limit: kernel reclaims aggressively above this
          MemoryMax = "16G"; # Hard limit: OOM kill if exceeded
          CPUWeight = 30;
          IOWeight = 30;
        };
      };
    })

    # Cargo/Rust build parallelism - tuned for i7-13700K (24 threads / 32GB RAM)
    # Peak memory ≈ jobs × ~2GB per rustc instance (debug builds with symbols)
    {
      environment.variables = {
        # 8 parallel crates × ~2GB = ~16GB peak, leaves ~16GB for system
        CARGO_BUILD_JOBS = "8";

        # Dev: 16 codegen units balances incremental compile speed vs memory
        # Must match Cargo.toml [profile.dev] codegen-units setting
        CARGO_PROFILE_DEV_CODEGEN_UNITS = "16";

        # Release: 1 = maximum optimization (full LTO, best inlining)
        CARGO_PROFILE_RELEASE_CODEGEN_UNITS = "1";
      };
    }
  ];
}
