# Notification System Configuration
# fnott notification daemon with custom styling

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          fnott
          libnotify
        ];
      };

      services.fnott = {
        enable = true;
        settings = {
          main = {
            notification-margin = 8;
            anchor = "top-right";
            layer = "overlay";

            # Dimensions
            max-width = 400;
            max-height = 200;
            min-width = 300;

            # Positioning

            # Styling
            border-size = 2;
            border-radius = 8;
            padding-horizontal = 12;
            padding-vertical = 8;

            # Icon
            # icon-size = 32;
            # max-icon-size = 64;

            # Progress bar
            progress-bar-height = 4;
            progress-bar-border-size = 0;
          };

          # Low urgency notifications
          low = {
            timeout = 5;
          };

          # Normal urgency notifications
          normal = {
            timeout = 10;
          };

          # Critical urgency notifications
          critical = {
            timeout = 0;
          };
        };
      };
    };
  };
}
