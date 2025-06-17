# Application Launcher Configuration (Tofi)
# Fuzzy application launcher with custom styling

{ lib, ... }:
{
  config = {
    home-manager.users.sinity = {
      programs.tofi = {
        enable = true;
        settings = {
          # Window sizing (similar to clipboard manager)
          width = 2000;
          height = 1000;

          # Font configuration
          font = "SauceCodePro Nerd Font Mono";
          font-size = lib.mkForce 16;

          # Layout
          anchor = "center";
          horizontal = false;
          num-results = 0;
          result-spacing = 4;

          # Padding and spacing
          padding-top = 20;
          padding-bottom = 20;
          padding-left = 20;
          padding-right = 20;

          # Prompt
          prompt-text = "❯ ";
          prompt-padding = 8;

          # Behavior
          history = true;
          hide-cursor = true;
          text-cursor = true;
          matching-algorithm = "fuzzy";

          # Performance
          late-keyboard-init = false;
          multi-instance = false;

          # Terminal for applications
          terminal = "kitty";
        };
      };
    };
  };
}