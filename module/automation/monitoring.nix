# Automation Monitoring
# Activity monitoring, system monitoring, and tracking services

{ pkgs, ... }:
let
  # ASBL mitigation script reference
  asbl-fooler = pkgs.writeShellApplication {
    name = "asbl-no-moar";
    runtimeInputs = [
      pkgs.wl-gammactl
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      echo "Setting gamma to 1.2"
      timeout -p 3500ms ${pkgs.wl-gammactl}/bin/wl-gammactl -g 1.2 || true
      echo "Gamma is back to 1.0"
    '';
  };
in
{
  config = {
    home-manager.users.sinity = {
      home.packages = with pkgs; [
        # From home/system.nix - system monitoring
        btop
        ncdu # disk space
        nitch # system fetch util

        # Modern file utilities
        dua # Disk usage analyzer (like ncdu but faster)
        yazi # Terminal file manager
        fselect # SQL-like file search

        # From home/system.nix - CLI utilities
        toipe # typing test in the terminal
        ttyper # cli typing test

        # From home/system.nix - Terminal toys
        cbonsai
        pipes
        tty-clock

        # From home/system.nix - Graphics tools
        mesa-demos
        vulkan-tools
        vulkan-validation-layers
        wayland-utils
        libva-utils
        glxinfo
        drm_info

        # ActivityWatch watchers
        aw-watcher-window-wayland
        aw-watcher-afk
      ];

      # Activity monitoring and tracking

      # From home/system.nix - btop configuration
      programs.btop = {
        enable = true;
        settings = {
          vim_keys = true;
          update_ms = 2000;
          show_cpu_freq = true;
          show_gpu = true;
          mem_graphs = true;
          proc_sorting = "cpu direct";
          proc_filter = false;
          tree_view = false;
          proc_per_core = true;
          proc_mem_bytes = true;
          cpu_graph_upper = "total";
          cpu_graph_lower = "user";
          cpu_invert_lower = true;
        };
      };

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
              target = "graphical-session.target";
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
  };
}
