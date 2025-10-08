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
  flakeRoot,
  ...
}:
let
  secretDir = ../secret;
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

  secretFiles =
    if builtins.pathExists secretDir then
      lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir secretDir)
    else
      { };

  secretNames = lib.mapAttrsToList (name: _: lib.removeSuffix ".age" name) secretFiles;

  secretsExcludedFromEnv = [
    "sinity-password"
    "root-password"
    "davfs2-secrets"
    "photoprism-admin-password"
  ];

  mkSecretExport =
    secretName:
    let
      envName = lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] secretName);
    in
    lib.optionalString (!lib.elem secretName secretsExcludedFromEnv) ''
      if [[ -r "${config.age.secrets.${secretName}.path}" ]]; then
        export ${envName}="$(<${config.age.secrets.${secretName}.path})"
      fi
    '';

  exportScript = lib.concatStringsSep "\n" (lib.filter (s: s != "") (map mkSecretExport secretNames));
in
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  config = {
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
            FLAKE = "${flakeRoot}";

            # XDG directories
            XDG_CONFIG_HOME = "\${HOME}/.config";
            XDG_CACHE_HOME = "\${HOME}/.cache";
            XDG_DATA_HOME = "\${HOME}/.local/share";
            XDG_STATE_HOME = "\${HOME}/.local/state";
          };

          packages = lib.mkAfter (
            with pkgs;
            [
              nix-output-monitor
              nvd
              cachix
              nix-direnv
              nix-direnv-flakes
              killall
              procps
              psmisc
              iotop
              entr # Perform action when file changes
              file # Show file information
              tldr
              xdg-utils
              xxd
              graphicsmagick
            ]
          );

        };

        programs.zsh = {
          initContent = lib.mkBefore ''
            load_secrets() {
              ${lib.optionalString (exportScript != "") exportScript}
            }
            load_secrets || true
          '';
          shellAliases = {
            load-secrets = "load_secrets";
          };
        };

        nix = {
          gc = {
            automatic = true;
            dates = "weekly";
            options = "--delete-older-than 30d";
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
            "wireshark"
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

    age = {
      identityPaths = [
        "/etc/ssh/ssh_host_ed25519_key"
      ]
      ++ lib.optionals (builtins.pathExists "/home/${username}/.ssh/id_ed25519") [
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
            else if secretName == "photoprism-admin-password" then
              rootOwnedSpec // { path = "/run/agenix/photoprism-admin-password"; }
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
      if [ "$(id -un)" = "${username}" ] && [ -z "$DISPLAY" ]; then
        current_tty=$(tty 2>/dev/null || true)
        if [ "$current_tty" = "/dev/tty1" ]; then
          exec uwsm start hyprland-uwsm.desktop
        fi
      fi
    '';

    # === FOUNDATION SYSTEMD CONFIGURATION ===
    systemd = {
      # settings.Manager = "DefaultTimeoutStopSec=5s";
      sleep.extraConfig = ''
        AllowSuspend=yes
        AllowHibernation=yes
        AllowSuspendThenHibernate=yes
        AllowHybridSleep=yes
        HibernateState=disk
      '';

      tmpfiles.rules = [
        "d ${journaldBaseDir} 0750 systemd-journal systemd-journal -"
        "d ${journaldBaseDir}/journal 2750 systemd-journal systemd-journal -"
        "d ${bootMetricsDir} 0750 root root -"
        "d /realm/inbox 0755 ${username} users -"
        "d /realm/inbox/screenshot 0755 ${username} users -"
        "d /realm/inbox/mpv-screenshots 0755 ${username} users -"
      ];

      services.capture-boot-metrics = {
        description = "Capture boot timing metrics";
        after = [
          "multi-user.target"
          "systemd-journald.service"
        ];
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${captureBootMetrics}/bin/capture-boot-metrics";
        };
      };
    };

    # Journald configuration (from services.nix)
    services.journald = {
      extraConfig = ''
        Storage=persistent
        SystemMaxUse=250G
        SystemKeepFree=10G
        SystemMaxFileSize=200M
        SystemMaxFiles=0
        RuntimeMaxUse=1G
        Compress=yes
        SplitMode=uid
      '';
    };

  };
}
