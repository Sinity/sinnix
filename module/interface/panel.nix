# Panel Configuration (Waybar)
# Status bar with system information, workspaces, and notifications

{ pkgs, ... }:
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
            "network"
            "custom/notification"
          ];
          clock = {
            calendar = {
              format = {
                today = "<span color='#98971A'><b>{}</b></span>";
              };
            };
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
            format = "<span foreground='#98971A'> </span> {usage}%";
            format-alt = "<span foreground='#98971A'> </span> {avg_frequency} GHz";
            interval = 2;
          };
          memory = {
            format = "<span foreground='#689D6A'>󰟜 </span>{}%";
            format-alt = "<span foreground='#689D6A'>󰟜 </span>{used} GiB";
            interval = 2;
          };
          disk = {
            format = "<span foreground='#D65D0E'>󰋊 </span>{percentage_used}%";
            interval = 60;
          };
          network = {
            format-wifi = "<span foreground='#B16286'> </span> {signalStrength}%";
            format-ethernet = "<span foreground='#B16286'>󰀂 </span>";
            tooltip-format = "Connected to {essid} {ifname} via {gwaddr}";
            format-linked = "{ifname} (No IP)";
            format-disconnected = "<span foreground='#B16286'>󰖪 </span>";
          };
          tray = {
            icon-size = 20;
            spacing = 8;
          };
          pulseaudio = {
            format = "{icon} {volume}%";
            format-muted = "<span foreground='#458588'> </span> {volume}%";
            format-icons = {
              default = [ "<span foreground='#458588'> </span>" ];
            };
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
            format = "{icon} ";
            format-icons = {
              notification = "<span foreground='red'><sup></sup></span>  <span foreground='#CC241D'></span>";
              none = "  <span foreground='#CC241D'></span>";
              dnd-notification = "<span foreground='red'><sup></sup></span>  <span foreground='#CC241D'></span>";
              dnd-none = "  <span foreground='#CC241D'></span>";
              inhibited-notification = "<span foreground='red'><sup></sup></span>  <span foreground='#CC241D'></span>";
              inhibited-none = "  <span foreground='#CC241D'></span>";
              dnd-inhibited-notification = "<span foreground='red'><sup></sup></span>  <span foreground='#CC241D'></span>";
              dnd-inhibited-none = "  <span foreground='#CC241D'></span>";
            };
            return-type = "json";
            exec-if = "which swaync-client";
            exec = "swaync-client -swb";
            on-click = "swaync-client -t -sw";
            on-click-right = "swaync-client -d -sw";
            escape = true;
          };
        };

        style = builtins.readFile ../asset/waybar-style.css;
      };
    };
  };
}