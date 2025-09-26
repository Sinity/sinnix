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
  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;
  secretsExcludedFromEnv = [
    "sinity-password"
    "root-password"
    "davfs2-secrets"
  ];
  exportableSecrets = lib.filter (name: !(lib.elem name secretsExcludedFromEnv)) secretNames;
  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] secretName);
    in
    ''
      if [[ -r "${config.age.secrets.${secretName}.path}" ]]; then
        export ${envName}="$(<${config.age.secrets.${secretName}.path})"
      fi
    '';
  exportScript = lib.concatStringsSep "\n" (map mkSecretExport exportableSecrets);
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
        max-jobs = 4;
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
          "(^|/)(java|chromium|obsidian|google-chrome-(stable|beta))$"
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

    # === USER CONFIGURATION (from system/user.nix) ===
    home-manager = {
      useUserPackages = true;
      useGlobalPkgs = true;
      backupFileExtension = "backup";
      extraSpecialArgs = { inherit inputs username host; };
      users.${username} = {
        imports = [ ];
        # Disable Stylix theming for VSCode to avoid conflicts with custom settings
        stylix.targets.vscode.enable = false;
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
          file = {
            ".config/secrets/export-env.zsh" = {
              text = ''
                # shellcheck disable=SC2148

                ${exportScript}
              '';
            };
          };
        };

        programs.zsh = {
          initContent = lib.mkAfter ''
            load_secrets() {
              local export_file="$HOME/.config/secrets/export-env.zsh"
              if [ ! -r "$export_file" ]; then
                echo "load_secrets: export file not found" >&2
                return 1
              fi
              # shellcheck disable=SC1090
              source "$export_file"
            }

            # Load secrets as early as possible in the interactive shell lifecycle
            load_secrets || true
          '';
          shellAliases = {
            load-secrets = "load_secrets";
          };
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
          hashedPasswordFile = "/run/agenix/sinity-password";
        };
        root = {
          shell = pkgs.zsh;
          home = "/root";
          hashedPasswordFile = "/run/agenix/root-password";
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

    networking.firewall = {
      enable = true;
      allowedTCPPorts = [ 22 ];
    };
    services.gnome.gnome-keyring.enable = true;

    programs.gnupg.agent = {
      enable = true;
      enableSSHSupport = true;
    };

    boot.kernel.sysctl."kernel.unprivileged_userns_clone" = 1;

    age = {
      identityPaths = [
        "/etc/ssh/ssh_host_ed25519_key"
        "/home/${username}/.ssh/id_ed25519"
      ];
      secrets = lib.mapAttrs' (filename: _: {
        name = lib.removeSuffix ".age" filename;
        value =
          let
            secretName = lib.removeSuffix ".age" filename;
            defaultSpec = {
              owner = username;
              mode = "0400";
            };
            rootOwnedSpec = defaultSpec // {
              owner = "root";
              group = "root";
            };
          in
          {
            file = ../secret/${filename};
          }
          // (
            if secretName == "davfs2-secrets" then
              rootOwnedSpec
              // {
                mode = "0600";
                path = "/run/agenix/davfs2-secrets";
              }
            else if secretName == "sinity-password" then
              rootOwnedSpec // { path = "/run/agenix/sinity-password"; }
            else if secretName == "root-password" then
              rootOwnedSpec // { path = "/run/agenix/root-password"; }
            else
              defaultSpec
          );
      }) secretFiles;
    };

    programs.zsh.loginShellInit = ''
      if [ -z "$DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
        exec uwsm start hyprland-uwsm.desktop
      fi
    '';

    # === FOUNDATION SYSTEMD CONFIGURATION ===
    # systemd.settings.Manager = "DefaultTimeoutStopSec=5s";
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

    systemd.tmpfiles.rules = [
      "d /realm/inbox 0755 ${username} users -"
      "d /realm/inbox/screenshot 0755 ${username} users -"
      "d /realm/inbox/mpv-screenshots 0755 ${username} users -"
    ];

    # Journald configuration (from services.nix)
    services.journald = {
      extraConfig = ''
        SystemMaxUse=5G
        SystemKeepFree=2G
        SystemMaxFileSize=50M
        SystemMaxFiles=100000
        RuntimeMaxUse=1G
      '';
    };
  };
}
