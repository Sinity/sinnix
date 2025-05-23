# module/automation.nix
# Complete automation domain: services, scripts, monitoring, scheduling
{
  config,
  pkgs,
  lib,
  ...
}:
let
  inherit (lib) mkMerge;
  username = "sinity";

  # Script packages from home/scripts/scripts.nix
  wall-change = pkgs.writeShellScriptBin "wall-change" (
    builtins.readFile ./home/scripts/scripts/wall-change.sh
  );
  wallpaper-picker = pkgs.writeShellScriptBin "wallpaper-picker" (
    builtins.readFile ./home/scripts/scripts/wallpaper-picker.sh
  );
  runbg = pkgs.writeShellScriptBin "runbg" (builtins.readFile ./home/scripts/scripts/runbg.sh);
  lofi = pkgs.writeScriptBin "lofi" (builtins.readFile ./home/scripts/scripts/lofi.sh);
  toggle_blur = pkgs.writeScriptBin "toggle_blur" (
    builtins.readFile ./home/scripts/scripts/toggle_blur.sh
  );
  toggle_oppacity = pkgs.writeScriptBin "toggle_oppacity" (
    builtins.readFile ./home/scripts/scripts/toggle_oppacity.sh
  );
  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" (
    builtins.readFile ./home/scripts/scripts/toggle_waybar.sh
  );
  maxfetch = pkgs.writeScriptBin "maxfetch" (builtins.readFile ./home/scripts/scripts/maxfetch.sh);
  compress = pkgs.writeScriptBin "compress" (builtins.readFile ./home/scripts/scripts/compress.sh);
  extract = pkgs.writeScriptBin "extract" (builtins.readFile ./home/scripts/scripts/extract.sh);
  shutdown-script = pkgs.writeScriptBin "shutdown-script" (
    builtins.readFile ./home/scripts/scripts/shutdown-script.sh
  );
  show-keybinds = pkgs.writeScriptBin "show-keybinds" (
    builtins.readFile ./home/scripts/scripts/keybinds.sh
  );
  ascii = pkgs.writeScriptBin "ascii" (builtins.readFile ./home/scripts/scripts/ascii.sh);
  record = pkgs.writeScriptBin "record" (builtins.readFile ./home/scripts/scripts/record.sh);
  rofi-power-menu = pkgs.writeScriptBin "rofi-power-menu" (
    builtins.readFile ./home/scripts/scripts/rofi-power-menu.sh
  );
  power-menu = pkgs.writeScriptBin "power-menu" (
    builtins.readFile ./home/scripts/scripts/power-menu.sh
  );

  # ASBL mitigation script
  asbl-fooler = pkgs.writeShellApplication {
    name = "asbl-no-moar";
    runtimeInputs = [
      pkgs.wl-gammactl
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      # Set gamma high
      echo "Setting gamma to 1.2"
      timeout -p 3500ms ${pkgs.wl-gammactl}/bin/wl-gammactl -g 1.2 || true

      # Revert gamma to default
      echo "Gamma is back to 1.0"

      # The timer will trigger the next run after the specified interval
    '';
  };
in
{
  config = mkMerge [
    # System-level automation configuration
    {
      system.nixos.tags = [ "automation-domain-v0.3" ];

      # System services and daemons
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

      services = {
        # System journal management
        journald = {
          extraConfig = ''
            SystemMaxUse=50G
            SystemKeepFree=25G
            SystemMaxFileSize=10M
            SystemMaxFiles=5000000
            RuntimeMaxUse=2G
          '';
        };

        # File sharing automation
        transmission = {
          enable = true;
          settings = {
            script-torrent-done-enabled = false;
            ratio-limit-enabled = false;
            umask = 18; # 002
            download-dir = "/outer-realm/inbox";
            incomplete-dir-enabled = false;
            rpc-port = 9091;
          };
        };

        # AI model serving
        ollama = {
          enable = true;
          acceleration = "cuda";
        };
      };
    }

    # User-level automation configuration
    {
      home-manager.users.${username} = {
        home.packages = [
          # Wallpaper automation
          wall-change
          wallpaper-picker

          # Background process management
          runbg
          lofi

          # UI state automation
          toggle_blur
          toggle_oppacity
          toggle_waybar

          # System information
          maxfetch

          # File management automation
          compress
          extract

          # Power management
          shutdown-script
          power-menu
          rofi-power-menu

          # Documentation and help
          show-keybinds
          ascii

          # Media recording
          record

          # ASBL mitigation
          asbl-fooler
        ];

        # Activity monitoring and tracking
        services.activitywatch = {
          enable = true;
          package = pkgs.aw-server-rust;

          watchers = {
            awatcher = {
              package = pkgs.awatcher;
              settings = {
                idle-timeout-seconds = 60;
                poll-time-idle-seconds = 1;
                poll-time-window-seconds = 1;
              };
            };
          };
        };

        # ASBL mitigation and ActivityWatch systemd configuration
        systemd.user = {
          services = {
            asbl-no-moar = {
              Unit = {
                Description = "Wayland gamma poke to mitigate ASBL";
                After = [ "graphical-session.target" ];
              };
              Service = {
                Type = "simple";
                ExecStart = "${asbl-fooler}/bin/asbl-no-moar";
                Restart = "no";
              };
              Install = {
                WantedBy = [ "default.target" ];
              };
            };

            activitywatch-watcher-awatcher =
              let
                target = "hyprland-session.target";
              in
              {
                Unit = {
                  After = [ target ];
                  Requisite = [ target ];
                  PartOf = [ target ];
                };
                Install = {
                  WantedBy = [ target ];
                };
              };
          };

          timers.asbl-no-moar = {
            Unit = {
              Description = "Timer for asbl-no-moar service";
            };
            Timer = {
              OnBootSec = "2min";
              OnUnitActiveSec = "150s";
              AccuracySec = "1s";
              Persistent = true;
            };
            Install = {
              WantedBy = [ "timers.target" ];
            };
          };
        };
      };
    }
  ];
}
