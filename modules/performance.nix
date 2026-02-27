# Performance Tuning
#
# Philosophy: 32GB RAM is enough. Don't swap as working memory — OOM-kill
# runaway processes instead. Swap exists only as a brief buffer so earlyoom
# has time to react before the kernel OOM killer makes a worse choice.
{
  pkgs,
  lib,
  config,
  ...
}:
{
  config = lib.mkIf config.sinnix.machine.isDesktop {
    # Zram: small compressed swap buffer — just enough runway for earlyoom to
    # detect pressure and kill the right process. NOT working memory.
    # 10% of 32GB = 3.2GB compressed ≈ 6-8GB logical pages. Deliberately small:
    # large swap hides memory leaks and causes slow crawls instead of fast kills.
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      memoryPercent = 10;
    };

    boot.kernel.sysctl = {
      # swappiness=0: only swap to avoid OOM. Normal desktop workloads should
      # never touch swap — if they do, something is wrong and earlyoom should kill it.
      "vm.swappiness" = 0;
      # Keep inode/dentry cache hot — NixOS store paths are long and frequently
      # resolved. Reducing eviction pressure improves terminal startup latency.
      "vm.vfs_cache_pressure" = 50;
      # Flush dirty pages earlier to avoid bursty I/O spikes.
      "vm.dirty_background_ratio" = 5;
      "vm.dirty_ratio" = 10;
    };

    # Earlyoom: the actual OOM policy. Kill early, kill fast, notify.
    # At 8% free RAM (~2.5GB) earlyoom kills the biggest process.
    # This fires BEFORE swap fills, so the system never enters a swap death spiral.
    services.earlyoom = {
      enable = true;
      freeMemThreshold = 8;
      freeSwapThreshold = 50;
      enableNotifications = true;
    };

    # systemd-oomd needs explicit cgroup PSI config per-service; earlyoom is simpler
    systemd.oomd.enable = false;

    # Nix daemon: cap aggregate build memory so compilations can't starve
    # interactive work. IOWeight=50 yields disk bandwidth to desktop processes.
    systemd.services.nix-daemon.serviceConfig = {
      IOWeight = 50;
      MemoryHigh = "60%";
      ManagedOOMMemoryPressure = "kill";
    };

    # Ananicy: per-process nice/ioclass for desktop responsiveness
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
        # Compilers/linkers
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

        # LSPs and language servers
        { name = "rust-analyzer"; type = "Heavy_Build"; }
        { name = "pyrefly"; type = "Heavy_Build"; }
        { name = "nil"; type = "Light_Build"; }
        { name = "nixd"; type = "Light_Build"; }
        { name = "typescript-language-server"; type = "Light_Build"; }
        { name = "gopls"; type = "Light_Build"; }

        # AI tools
        { name = "claude"; type = "Light_Build"; }
        { name = "gemini"; type = "Light_Build"; }
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
