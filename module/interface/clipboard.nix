# Clipboard Management Configuration
# Wayland clipboard utilities and persistent clipboard history

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          # Clipboard management
          wl-clip-persist # Keep clipboard content after application closes
          wl-clipboard # Wayland clipboard utilities
          clipse # TUI clipboard manager with persistent history
        ];
      };

      # === CLIPSE CONFIGURATION ===
      services.clipse = {
        enable = true;
        historySize = 99999;
        allowDuplicates = false;
        systemdTarget = "graphical-session.target";

        imageDisplay = {
          type = "kitty";
          scaleX = 9;
          scaleY = 9;
          heightCut = 2;
        };

        keyBindings = {
          choose = "enter";
          clearSelected = "D"; # Vim-like: D for delete to end
          down = "j"; # Vim navigation
          up = "k"; # Vim navigation
          end = "G"; # Vim: go to end
          home = "g"; # Single g for beginning (practical compromise)
          filter = "/"; # Already vim-like
          more = "?"; # Already vim-like
          nextPage = "l"; # Vim: right
          prevPage = "h"; # Vim: left
          preview = "v"; # Vim-like: v for visual
          quit = "q"; # Already vim-like
          remove = "d"; # Single d for delete (practical)
          selectDown = "J"; # Shift+j for selection
          selectUp = "K"; # Shift+k for selection
          selectSingle = "V"; # Vim: visual line mode
          togglePin = "m"; # Vim-like: m for mark
          togglePinned = "M"; # Show marked items
          yankFilter = "y"; # Vim: yank
        };
      };
    };
  };
}
