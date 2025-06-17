# Notification System Configuration
# SwayNC notification center with custom styling

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          swaynotificationcenter
        ];
      };

      # === SWAYNC (from swaync/default.nix) ===
      services.swaync = {
        enable = true;
        settings = {
          "$schema" = "/etc/xdg/swaync/configSchema.json";
          positionX = "right";
          positionY = "top";
          layer = "overlay";
          cssPriority = "application";
          control-center-layer = "top";
          control-center-margin-top = 8;
          control-center-margin-bottom = 8;
          control-center-margin-right = 8;
          control-center-margin-left = 8;
          notification-2fa-action = true;
          notification-inline-replies = false;
          notification-icon-size = 64;
          notification-body-image-height = 100;
          notification-body-image-width = 200;
          timeout = 10;
          timeout-low = 5;
          timeout-critical = 0;
          fit-to-screen = true;
          relative-timestamps = true;
          control-center-width = 500;
          control-center-height = 600;
          notification-window-width = 500;
          keyboard-shortcuts = true;
          image-visibility = "when-available";
          transition-time = 200;
          hide-on-clear = false;
          hide-on-action = true;
          script-fail-notify = true;
          scripts = {
            example-script = {
              exec = "echo 'Do something...'";
              urgency = "Normal";
            };
            example-action-script = {
              exec = "echo 'Do something actionable!'";
              urgency = "Normal";
            };
          };

          notification-visibility = {
            example-name = {
              state = "muted";
              urgency = "Low";
              app-name = "Spotify";
            };
          };

          widgets = [
            "inhibitors"
            "title"
            "dnd"
            "notifications"
            "mpris"
            "volume"
          ];

          widget-config = {
            inhibitors = {
              text = "Inhibitors";
              button-text = "Clear All";
              clear-all-button = true;
            };
            title = {
              text = "Notifications";
              clear-all-button = true;
              button-text = "Clear All";
            };
            dnd = {
              text = " Do Not Disturb";
            };
            label = {
              max-lines = 5;
              text = "Label Text";
            };
            mpris = {
              image-size = 85;
              image-radius = 5;
            };
            volume = {
              label = "";
              expand-button-label = "";
              collapse-button-label = "";
              show-per-app = true;
              show-per-app-icon = true;
              show-per-app-label = false;
            };
            "backlight#mobile" = {
              label = " 󰃠 ";
              device = "panel";
            };
          };
        };

        style = builtins.readFile ../asset/swaync-style.css;
      };
    };
  };
}
