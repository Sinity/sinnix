# Performance Tuning
#
# Zram for swap buffer, earlyoom to kill before freeze, ananicy for scheduling.
{
  pkgs,
  lib,
  config,
  ...
}:
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    # Zram: compressed swap buffer so kernel doesn't freeze when RAM fills
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      memoryPercent = 10;
    };

    # Earlyoom: kill biggest process at 5% free instead of freezing
    services.earlyoom = {
      enable = true;
      freeMemThreshold = 5;
      freeSwapThreshold = 10;
      enableNotifications = true;
    };

    # systemd-oomd is useless without explicit cgroup PSI config; earlyoom replaces it
    systemd.oomd.enable = false;

    # Ananicy for desktop responsiveness
    services.ananicy = {
      enable = true;
      package = pkgs.ananicy-cpp;
      rulesProvider = pkgs.ananicy-rules-cachyos;
      settings.apply_oom_score_adj = true;

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
        # Compilers/linkers - low priority
        {
          name = "gcc";
          type = "Heavy_Build";
        }
        {
          name = "g++";
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
          name = "mold";
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

        # LSPs and language servers - heavy background indexers
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

        # AI tools - background work, not interactive
        {
          name = "claude";
          type = "Light_Build";
        }
        {
          name = "gemini";
          type = "Light_Build";
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
