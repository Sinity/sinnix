# Foundation Domain Module
# Core system bootstrap, users, security
# Consolidates: system.nix, user.nix, security.nix

{
  pkgs,
  inputs,
  username,
  host,
  config,
  lib,
  ...
}:
let
  # Find all .age files in the secret directory
  secretFiles = lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir ../secret);
in
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  config = {
    system.nixos.tags = [ "foundation-domain-v0.3" ];

    # === SYSTEM CONFIGURATION (from system/system.nix) ===
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
        max-jobs = 2;
        cores = 0;
        allowed-users = [ "${username}" ];
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
        allowBroken = true;
        allowAliases = true;
      };
      overlays = [ inputs.nur.overlays.default ];
    };

    environment = {
      systemPackages = with pkgs; [
        wget
        git
        nix-output-monitor
        nvd
        cachix
        nix-direnv
        nix-direnv-flakes

        # Core system utilities from home/system.nix
        killall
        procps
        psmisc
        iotop

        # Hardware management from home/system.nix
        hwinfo
        inxi
        dmidecode
        lshw
        pciutils
        usbutils

        # Storage utilities from home/system.nix
        btrfs-progs
        hdparm
        smartmontools
        nvme-cli

        # Networking from home/system.nix
        iputils
        ethtool
        iftop
        iperf3

        # System-level graphics packages from home/system.nix
        mesa
        libGL
        libglvnd

        # Hardware diagnostics from home/system.nix
        cpuid
        i7z
        mcelog
        memtester
        numactl
        hw-probe
        hwdata

        # Storage utilities from home/system.nix
        xfsprogs
        e2fsprogs
        lvm2
        parted
        fio
        ioping
        udisks2
        extundelete

        # System utilities from home/system.nix
        bpftrace
        entr # Perform action when file changes
        file # Show file information
        tldr
        xdg-utils
        xxd
        graphicsmagick
      ];
      variables = {
        FLAKE = "/realm/project/sinnix";
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
          "(^|/)(java|chromium|obsidian|google-chrome-stable)$"
          "--avoid"
          "(^|/)(init|systemd|sshd)$"
        ];
      };

      # PostgreSQL with TimescaleDB for Sinex (exocortex service)
      postgresql = {
        enable = true;
        package = pkgs.postgresql_16;
        dataDir = "/var/lib/postgresql/16";
        settings = {
          shared_preload_libraries = "timescaledb";
          max_connections = 100;
          shared_buffers = "256MB";
          effective_cache_size = "1GB";
          maintenance_work_mem = "64MB";
          checkpoint_completion_target = 0.9;
          wal_buffers = "16MB";
          default_statistics_target = 100;
          random_page_cost = 1.1;
          effective_io_concurrency = 200;
          work_mem = "4MB";
          min_wal_size = "1GB";
          max_wal_size = "4GB";
        };
        extensions = ps: with ps; [ timescaledb ];
        authentication = pkgs.lib.mkOverride 10 ''
          # TYPE  DATABASE        USER            ADDRESS                 METHOD
          local   all             all                                     trust
          host    all             all             127.0.0.1/32            trust
          host    all             all             ::1/128                 trust
        '';
        ensureDatabases = [ "sinex" ];
        ensureUsers = [
          {
            name = "sinity";
            ensureDBOwnership = true;
            ensureClauses = {
              superuser = true;
              createrole = true;
              createdb = true;
            };
          }
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

    # === USER CONFIGURATION (from system/user.nix) ===
    home-manager = {
      useUserPackages = true;
      useGlobalPkgs = true;
      backupFileExtension = "backup";
      extraSpecialArgs = { inherit inputs username host; };
      users.${username} = {
        imports = [ ];
        home = {
          username = "${username}";
          homeDirectory = "/home/${username}";
          stateVersion = "24.05";

          sessionVariables = {
            # Core system paths from environment.nix
            FLAKE = "/realm/project/sinnix";

            # XDG directories
            XDG_CONFIG_HOME = "\${HOME}/.config";
            XDG_CACHE_HOME = "\${HOME}/.cache";
            XDG_DATA_HOME = "\${HOME}/.local/share";
            XDG_STATE_HOME = "\${HOME}/.local/state";
          };

          # Removed ~/scripts from PATH - scripts now embedded in automation.nix
        };
        programs.home-manager.enable = true;
      };
    };

    users = {
      mutableUsers = false;
      users = {
        ${username} = {
          isNormalUser = true;
          extraGroups = [
            "networkmanager"
            "wheel"
            "users"
            "video"
          ];
          shell = pkgs.zsh;
          hashedPassword = "REDACTED_HASH";
        };
        root = {
          shell = pkgs.zsh;
          home = "/root";
          hashedPassword = "REDACTED_HASH";
        };
      };
    };

    # === SECURITY CONFIGURATION (from system/security.nix) ===
    security = {
      rtkit.enable = true;
      sudo.wheelNeedsPassword = false;
      pam.services.hyprlock = { };
      wrappers.bubblewrap = {
        source = "${pkgs.bubblewrap}/bin/bwrap";
        owner = "root";
        group = "root";
        setuid = true;
      };
    };

    networking.firewall.enable = false;
    services.gnome.gnome-keyring.enable = true;

    programs.gnupg.agent = {
      enable = true;
      enableSSHSupport = true;
    };

    boot.kernel.sysctl."kernel.unprivileged_userns_clone" = 1;

    age = {
      identityPaths = [ "/home/sinity/.ssh/id_ed25519" ];
      secrets = lib.mapAttrs' (filename: _: {
        name = lib.removeSuffix ".age" filename;
        value = {
          file = ../secret/${filename};
          owner = "sinity";
        };
      }) secretFiles;
    };

    programs.zsh.loginShellInit = lib.concatStringsSep "\n" (
      [
        # Auto-start Hyprland with UWSM on TTY1
        ''
          if [ -z "$DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
            exec uwsm start hyprland-uwsm.desktop
          fi
        ''
      ]
      ++ lib.mapAttrsToList (
        filename: _:
        let
          secretName = lib.removeSuffix ".age" filename;
          envName = lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] secretName);
        in
        ''export ${envName}="$(<${config.age.secrets.${secretName}.path})"''
      ) secretFiles
    );

    # === FOUNDATION SYSTEMD CONFIGURATION ===
    systemd.extraConfig = "DefaultTimeoutStopSec=5s";
    systemd.sleep = {
      extraConfig = ''
        AllowSuspend=yes
        AllowHibernation=yes
        AllowSuspendThenHibernate=yes
        AllowHybridSleep=yes
        HibernateMode=reboot
        HibernateState=disk
      '';
    };

    # Journald configuration (from services.nix)
    services.journald = {
      extraConfig = ''
        SystemMaxUse=50G
        SystemKeepFree=25G
        SystemMaxFileSize=10M
        SystemMaxFiles=5000000
        RuntimeMaxUse=2G
      '';
    };
  };
}
