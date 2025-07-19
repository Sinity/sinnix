# Panel Configuration (Waybar)
# Status bar with system information, workspaces, and notifications

{ pkgs, lib, ... }:
{
  config = {
    home-manager.users.sinity = {
      programs.waybar = {
        enable = true;
        systemd = {
          enable = true;
          target = "graphical-session.target";
        };
        package = pkgs.waybar.overrideAttrs (oa: {
          mesonFlags = (oa.mesonFlags or [ ]) ++ [ "-Dexperimental=true" ];
        });
        
        # Use stylix theming with better font weight and color-coded indicators
        style = lib.mkAfter ''
          * {
            font-family: "SauceCodePro Nerd Font Mono", monospace;
            font-weight: 600;
          }
          
          /* Constant colorful system indicators for easy distinction */
          #cpu {
            color: #fb4934; /* Red */
          }
          
          #memory {
            color: #fabd2f; /* Yellow */
          }
          
          #disk {
            color: #b8bb26; /* Green */
          }
          
          #pulseaudio {
            color: #83a598; /* Blue */
          }
          
          #pulseaudio.muted {
            color: #665c54; /* Gray when muted */
          }
        '';

        settings.mainBar = {
          position = "bottom";
          layer = "top";
          height = 30;
          margin-top = 0;
          margin-bottom = 0;
          margin-left = 0;
          margin-right = 0;
          modules-left = [
            "custom/launcher"
            "hyprland/workspaces"
            "tray"
          ];
          modules-center = [ "clock" ];
          modules-right = [
            "cpu"
            "memory"
            "disk"
            "pulseaudio"
            "custom/notification"
          ];
          clock = {
            format = "  {:%H:%M}";
            tooltip = "true";
            tooltip-format = ''
              <big>{:%Y %B}</big>
              <tt><small>{calendar}</small></tt>'';
            format-alt = "  {:%d/%m}";
          };
          "hyprland/workspaces" = {
            active-only = false;
            disable-scroll = false;
            format = "{icon}";
            on-click = "activate";
            show-special = false; # Hide special workspaces
            format-icons = {
              "1" = "I";
              "2" = "II";
              "3" = "III";
              "4" = "IV";
              "5" = "V";
              "active" = "󰮯";
              "default" = "󰊠";
              "special" = "󰠱";
              sort-by-number = true;
            };
            persistent-workspaces = {
              "1" = [ ];
              "2" = [ ];
              "3" = [ ];
              "4" = [ ];
              "5" = [ ];
            };
          };
          cpu = {
            format = " {usage}%";
            format-alt = " {avg_frequency}GHz";
            interval = 2;
          };
          memory = {
            format = " {percentage}%";
            format-alt = " {used}GB";
            interval = 2;
          };
          disk = {
            format = " {percentage_used}%";
            interval = 60;
          };
          tray = {
            icon-size = 20;
            spacing = 8;
          };
          pulseaudio = {
            format = " {volume}%";
            format-muted = " MUTED";
            scroll-step = 5;
            on-click = "pamixer -t";
          };
          "custom/launcher" = {
            format = "";
            on-click = "tofi-drun --drun-launch=true";
            tooltip = "false";
          };
          "custom/notification" = {
            tooltip = false;
            format = "  ";
            on-click = "fnottctl dismiss";
            on-click-right = "fnottctl actions";
          };
        };

      };
    };
  };
}