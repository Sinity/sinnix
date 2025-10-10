{
  pkgs,
  inputs,
  username,
  host,
  lib,
  ...
}:
let
  journaldBaseDir = "/realm/data/syslog";
  bootMetricsDir = "${journaldBaseDir}/boot-metrics";
  captureBootMetrics = pkgs.writeShellApplication {
    name = "capture-boot-metrics";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.findutils
      pkgs.util-linux
      pkgs.systemd
    ];
    text = ''
      set -euo pipefail

      BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
      OUT_DIR="${bootMetricsDir}/''${BOOT_ID}"
      mkdir -p "''${OUT_DIR}"

      systemd-analyze time > "''${OUT_DIR}/time.txt"
      systemd-analyze blame > "''${OUT_DIR}/blame.txt"
      systemd-analyze critical-chain > "''${OUT_DIR}/critical-chain.txt"
      systemd-analyze plot > "''${OUT_DIR}/boot.svg"

      journalctl -b -p 0..3 > "''${OUT_DIR}/journal-errors.log" || true
      dmesg > "''${OUT_DIR}/dmesg.log"
    '';
  };

in
{
  config = {
    nix = {
      settings = {
        auto-optimise-store = true;
        experimental-features = [
          "nix-command"
          "flakes"
        ];
        trusted-users = [
          "sinity"
          "root"
          "@wheel"
        ];
        substituters = [
          "https://cache.nixos.org/"
          "https://sinity.cachix.org"
          "https://nix-gaming.cachix.org"
        ];
        trusted-public-keys = [
          "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
          "sinity.cachix.org-1:i5YsUuuRv9r790gdwwE+FiJiUcWULV1lEOmKE50Y+TI="
          "nix-gaming.cachix.org-1:nbjlureqMbRAxR1gJ/f3hxemL9svXaZF/Ees8vCUUs4="
        ];
        max-jobs = 4;
        cores = 0;
        allowed-users = [
          "root"
          "@wheel"
          username
        ];
      };

      daemonCPUSchedPolicy = "idle";
      daemonIOSchedClass = "idle";
      daemonIOSchedPriority = 6;

      gc = {
        automatic = true;
        dates = "weekly";
        options = "--delete-older-than 30d";
      };

      optimise = {
        automatic = true;
        dates = [ "weekly" ];
      };
    };

    nixpkgs = {
      config = {
        allowUnfree = true;
        allowAliases = true;
      };
      overlays = [ inputs.nur.overlays.default ];
    };

    environment = {
      systemPackages = with pkgs; [
        wget
        git

        hwinfo
        inxi
        dmidecode
        lshw
        pciutils
        usbutils

        btrfs-progs
        hdparm
        smartmontools
        nvme-cli

        iputils
        ethtool
        iftop
        iperf3

        mesa
        libGL
        libglvnd

        cpuid
        i7z
        mcelog
        memtester
        numactl
        hw-probe
        hwdata

        xfsprogs
        e2fsprogs
        lvm2
        parted
        fio
        ioping
        udisks2
        extundelete

        bpftrace
      ];
      variables = {
        REALM_ROOT = "/realm";
      };
    };

    programs = {
      direnv = {
        enable = true;
        silent = true;
        enableZshIntegration = true;
        enableBashIntegration = true;
        nix-direnv.enable = true;
      };
      dconf.enable = true;
      zsh.enable = true;
    };

    systemd.coredump.enable = true;

    services = {
      dbus.enable = true;
      xserver.xkb.layout = "pl";
      earlyoom = {
        enable = true;
        enableNotifications = true;
        freeMemThreshold = 5;
        freeSwapThreshold = 5;
        reportInterval = 5;
        extraArgs = [
          "-g"
          "-p"
          "--prefer"
          "(^|/)(java|chromium|obsidian|google-chrome(-stable)?)$"
          "--avoid"
          "(^|/)(init|systemd|sshd)$"
        ];
      };
    };

    console.keyMap = "pl2";
    console.font = "Lat2-Terminus16";
    time.timeZone = "Europe/Warsaw";
    i18n.defaultLocale = "en_US.UTF-8";
    i18n.extraLocaleSettings = {
      LC_ADDRESS = "pl_PL.UTF-8";
      LC_IDENTIFICATION = "pl_PL.UTF-8";
      LC_MEASUREMENT = "pl_PL.UTF-8";
      LC_MONETARY = "pl_PL.UTF-8";
      LC_NAME = "pl_PL.UTF-8";
      LC_NUMERIC = "pl_PL.UTF-8";
      LC_PAPER = "pl_PL.UTF-8";
      LC_TELEPHONE = "pl_PL.UTF-8";
      LC_TIME = "pl_PL.UTF-8";
    };

    system.stateVersion = "24.05";

    security = {
      rtkit.enable = true;
      sudo.wheelNeedsPassword = false;
      pam.services.hyprlock = { };
    };

    networking.firewall = {
      enable = true;
      allowedTCPPorts = [ 22 ];
      allowedUDPPortRanges = [
        {
          from = 60000;
          to = 61000;
        }
      ];
    };
    services.gnome.gnome-keyring.enable = true;

    programs.gnupg.agent = {
      enable = true;
      enableSSHSupport = true;
    };

    boot.kernel.sysctl."kernel.unprivileged_userns_clone" = 1;

    systemd.services.capture-boot-metrics = {
      description = "Capture boot metrics and logs";
      wantedBy = [ "multi-user.target" ];
      after = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
      };
      environment.BOOT_METRICS_DIR = bootMetricsDir;
    };

    systemd.tmpfiles.rules = [
      "d ${journaldBaseDir} 0755 ${username} ${username} -"
      "d ${bootMetricsDir} 0755 ${username} ${username} -"
      "z /dev/input/event* 0640 root input wireshark"
    ];

    services.journald.extraConfig = ''
      Compress=yes
      SystemMaxUse=512M
      RuntimeMaxUse=128M
    '';

    services.logrotate.enable = true;
  };
}
