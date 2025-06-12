# Desktop Environment Configuration
# Desktop utilities, applications, terminal, notifications, and services

{
  lib,
  pkgs,
  config,
  ...
}:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          # Clipboard management
          wl-clip-persist # Keep clipboard content after application closes
          wl-clipboard # Wayland clipboard utilities
          clipse # TUI clipboard manager with persistent history

          # Notification center from swaync/default.nix
          swaynotificationcenter

          # Color and appearance
          swaybg # Wallpaper utility
          hyprpicker # Color picker
          wl-gammactl # Adjust gamma
          wlsunset # Night light/blue light filter
          redshift # Adjust color temperature (X11/Wayland)

          # Dependencies and libraries
          glib # GLib library
          wayland # Wayland protocol library
          egl-wayland # EGL support for Wayland
          direnv # Directory environment manager

          # XDG mimes dependencies
          junction

          # Desktop applications from desktop-apps.nix
          libreoffice
          nautilus
          obsidian
          taskwarrior3
          timewarrior
          bleachbit # cache cleaner
          ddcutil # Query and change Linux monitor settings
          transmission_3-gtk # BitTorrent client

          # Audio control alternatives
          pulsemixer # TUI alternative to pavucontrol
          pwvucontrol # Modern pipewire GUI

          # Bluetooth alternatives
          bluetuith # Better TUI bluetooth manager
          blueman # GUI bluetooth manager

          # Music
          ncspot # Terminal Spotify client

          evtest # Input device event monitor
          meld # Diff tool
          piper # Mouse configuration
          android-tools
          android-file-transfer
          hledger # Accounting
          llm # CLI for LLMs
          single-file-cli # Save web pages
          programmer-calculator
          bc # Calculator
          calc # Another calculator

          soundwireserver # Audio streaming (used by hyprland keybind)
          imgur-screenshot
          usbview
          strace # System call tracer
          ltrace # Library call tracer
          nvitop # NVIDIA GPU monitoring
          cage # Wayland kiosk
          wayland-protocols # Wayland development
          vkmark # Vulkan benchmark
          dtach # Screen alternative
          lnch # Application launcher
          at # Job scheduler
        ];

        # Environment variables for proper Wayland/Hyprland operation
        sessionVariables = {
          BROWSER = "google-chrome-beta";
          TERM = "kitty";
          TERMINAL = "kitty";

          # Wayland/Hyprland specific
          XDG_SESSION_TYPE = "wayland";
          XDG_CURRENT_DESKTOP = "Hyprland";
          XDG_SESSION_DESKTOP = "Hyprland";
          XDG_DESKTOP_PORTAL_DIR = "/run/current-system/sw/share/xdg-desktop-portal/portals";
          GDK_BACKEND = "wayland";
          SDL_VIDEODRIVER = "wayland";
          CLUTTER_BACKEND = "wayland";
          MOZ_ENABLE_WAYLAND = "1";
          ANKI_WAYLAND = "1";
          NIXOS_OZONE_WL = "1";
          ELECTRON_OZONE_PLATFORM_HINT = "wayland";
          OZONE_PLATFORM = "wayland";
          OZONE_PLATFORM_HINT = "wayland";
          LIBVA_DRIVER_NAME = "nvidia";
          GBM_BACKEND = "nvidia-drm";
          __GLX_VENDOR_LIBRARY_NAME = "nvidia";
          WLR_NO_HARDWARE_CURSORS = "1";
          __GL_GSYNC_ALLOWED = "1";
          __GL_VRR_ALLOWED = "1";
          _JAVA_AWT_WM_NONEREPARENTING = "1";
          SSH_AUTH_SOCK = "/run/user/1000/keyring/ssh";
          DIRENV_LOG_FORMAT = "";
          NIXPKGS_ALLOW_UNFREE = "1";
          WINEDLLOVERRIDES = "winemenubuilder.exe=d";
        };
      };

      # UWSM systemd services for autostart applications
      systemd.user.services = {
        wl-clip-persist = {
          Unit = {
            Description = "Wayland clipboard persistence";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };

        nm-applet = {
          Unit = {
            Description = "NetworkManager applet";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
            Restart = "on-failure";
            RestartSec = 1;
          };
          Install = {
            WantedBy = [ "graphical-session.target" ];
          };
        };
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

      # === WAYBAR (from home/desktop/waybar) ===
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

      # === KITTY CONFIGURATION (from home/kitty.nix) ===
      programs.kitty = {
        enable = true;
        settings = {
          window_padding_width = 10;
          scrollback_lines = 9999999;
          enable_audio_bell = "no";
          background = "#000000"; # Pure black background
          mouse_hide_wait = 60;
          wheel_scroll_multiplier = 0.5;
          touch_scroll_multiplier = 0.5;
          cursor_trail = 3;
          confirm_os_window_close = 0;
          # Enable remote control for Sinex integration
          allow_remote_control = "yes";
          listen_on = "unix:/tmp/kitty";
          open_url_with = "xdg-open";
          detect_urls = "yes";
          url_prefixes = "http https file ftp";
          url_style = "single";
          allow_hyperlinks = "yes";
          tab_title_template = "{title}";
          active_tab_font_style = "normal";
          inactive_tab_font_style = "normal";
          tab_bar_style = "powerline";
          tab_powerline_style = "angled";
        };
        extraConfig = ''
          map ctrl+shift+f12 debug_config

          # Shell integration for command tracking
          shell_integration enabled
        '';
        keybindings = {
          "alt+1" = "goto_tab 1";
          "alt+2" = "goto_tab 2";
          "alt+3" = "goto_tab 3";
          "alt+4" = "goto_tab 4";
          "ctrl+shift+left" = "no_op";
          "ctrl+shift+right" = "no_op";
        };
      };

      # === TOFI CONFIGURATION ===
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

      # === SWAYNC CONFIGURATION (from home/desktop/swaync) ===
      services.swaync = {
        enable = true;
        settings = {
          positionX = "right";
          positionY = "top";
          layer = "overlay";
          layer-shell = "true";
          cssPriority = "application";
          control-center-margin-top = 10;
          control-center-margin-bottom = 10;
          control-center-margin-right = 10;
          control-center-margin-left = 10;
          notification-icon-size = 64;
          notification-body-image-height = 128;
          notification-body-image-width = 200;
          timeout = 10;
          timeout-low = 5;
          timeout-critical = 0;
          fit-to-screen = true;
          control-center-width = 400;
          control-center-height = 650;
          notification-window-width = 350;
          keyboard-shortcuts = true;
          image-visibility = "when-available";
          transition-time = 200;
          hide-on-clear = false;
          hide-on-action = true;
          script-fail-notify = true;
          widgets = [
            "title"
            "menubar#desktop"
            "volume"
            "backlight#mobile"
            "mpris"
            "dnd"
            "notifications"
          ];
          widget-config = {
            title = {
              text = "Notifications";
              clear-all-button = true;
              button-text = " Clear All ";
            };
            "menubar#desktop" = {
              "menu#powermode-buttons" = {
                label = " 󰌪 ";
                position = "left";
                actions = [
                  {
                    label = "Performance";
                    command = "powerprofilesctl set performance";
                  }
                  {
                    label = "Balanced";
                    command = "powerprofilesctl set balanced";
                  }
                  {
                    label = "Power-saver";
                    command = "powerprofilesctl set power-saver";
                  }
                ];
              };
              "menu#screenshot" = {
                label = "  ";
                position = "left";
                actions = [
                  {
                    label = "󰹑  Whole screen";
                    command = "grimblast --notify --cursor --freeze copy output";
                  }
                  {
                    label = "󰩭  Window / Region";
                    command = "grimblast --notify --cursor --freeze copy area";
                  }
                ];
              };
              "menu#power-buttons" = {
                label = "  ";
                position = "left";
                actions = [
                  {
                    label = "  Lock";
                    command = "swaylock";
                  }
                  {
                    label = "  Reboot";
                    command = "systemctl reboot";
                  }
                  {
                    label = "  Shut down";
                    command = "systemctl poweroff";
                  }
                ];
              };
            };
            "backlight#mobile" = {
              label = " 󰃠 ";
              device = "panel";
            };
            volume = {
              label = "";
              expand-button-label = "";
              collapse-button-label = "";
              show-per-app = true;
              show-per-app-icon = true;
              show-per-app-label = false;
            };
            dnd = {
              text = " Do Not Disturb";
            };
            mpris = {
              image-size = 85;
              image-radius = 5;
            };
          };
        };

        style = builtins.readFile ../asset/swaync-style.css;
      };

      # === XDG MIMES (from home/xdg-mimes.nix) ===
      xdg = {
        configFile."mimeapps.list".force = true;
        mimeApps = {
          enable = true;
          associations.added = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "com.interversehq.qView.desktop" ];
            "image/gif" = [ "com.interversehq.qView.desktop" ];
            "image/jpeg" = [ "com.interversehq.qView.desktop" ];
            "image/jpg" = [ "com.interversehq.qView.desktop" ];
            "image/png" = [ "com.interversehq.qView.desktop" ];
            "image/svg+xml" = [ "com.interversehq.qView.desktop" ];
            "image/tiff" = [ "com.interversehq.qView.desktop" ];
            "image/vnd.microsoft.icon" = [ "com.interversehq.qView.desktop" ];
            "image/webp" = [ "com.interversehq.qView.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "audio/x-matroska" = [ "mpv.desktop" ];
            "video/mp2t" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mpeg" = [ "mpv.desktop" ];
            "video/ogg" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-flv" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "video/x-msvideo" = [ "mpv.desktop" ];
            "inode/directory" = [
              "nautilus.desktop"
              "org.gnome.Nautilus.desktop"
            ];
            "text/html" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome-beta.desktop" ];
            "application/vnd.oasis.opendocument.text" = [ "libreoffice.desktop" ];
            "application/vnd.oasis.opendocument.spreadsheet" = [ "libreoffice.desktop" ];
            "application/vnd.oasis.opendocument.presentation" = [ "libreoffice.desktop" ];
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" = [
              "libreoffice.desktop"
            ];
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" = [ "libreoffice.desktop" ];
            "application/vnd.openxmlformats-officedocument.presentationml.presentation" = [
              "libreoffice.desktop"
            ];
            "application/msword" = [ "libreoffice.desktop" ];
            "application/vnd.ms-excel" = [ "libreoffice.desktop" ];
            "application/vnd.ms-powerpoint" = [ "libreoffice.desktop" ];
            "application/rtf" = [ "libreoffice.desktop" ];
            "application/pdf" = [ "org.gnome.Evince.desktop" ];
            "terminal" = [ "kitty.desktop" ];
            "application/zip" = [ "org.gnome.FileRoller.desktop" ];
            "application/rar" = [ "org.gnome.FileRoller.desktop" ];
            "application/7z" = [ "org.gnome.FileRoller.desktop" ];
            "application/*tar" = [ "org.gnome.FileRoller.desktop" ];
          };
          defaultApplications = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "com.interversehq.qView.desktop" ];
            "image/gif" = [ "com.interversehq.qView.desktop" ];
            "image/jpeg" = [ "com.interversehq.qView.desktop" ];
            "image/jpg" = [ "com.interversehq.qView.desktop" ];
            "image/png" = [ "com.interversehq.qView.desktop" ];
            "image/svg+xml" = [ "com.interversehq.qView.desktop" ];
            "image/tiff" = [ "com.interversehq.qView.desktop" ];
            "image/vnd.microsoft.icon" = [ "com.interversehq.qView.desktop" ];
            "image/webp" = [ "com.interversehq.qView.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "audio/x-matroska" = [ "mpv.desktop" ];
            "video/mp2t" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mpeg" = [ "mpv.desktop" ];
            "video/ogg" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-flv" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "video/x-msvideo" = [ "mpv.desktop" ];
            "inode/directory" = [
              "nautilus.desktop"
              "org.gnome.Nautilus.desktop"
            ];
            "text/html" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome-beta.desktop" ];
            "application/vnd.oasis.opendocument.text" = [ "libreoffice.desktop" ];
            "application/vnd.oasis.opendocument.spreadsheet" = [ "libreoffice.desktop" ];
            "application/vnd.oasis.opendocument.presentation" = [ "libreoffice.desktop" ];
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" = [
              "libreoffice.desktop"
            ];
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" = [ "libreoffice.desktop" ];
            "application/vnd.openxmlformats-officedocument.presentationml.presentation" = [
              "libreoffice.desktop"
            ];
            "application/msword" = [ "libreoffice.desktop" ];
            "application/vnd.ms-excel" = [ "libreoffice.desktop" ];
            "application/vnd.ms-powerpoint" = [ "libreoffice.desktop" ];
            "application/rtf" = [ "libreoffice.desktop" ];
            "application/pdf" = [ "org.gnome.Evince.desktop" ];
            "terminal" = [ "kitty.desktop" ];
            "application/zip" = [ "org.gnome.FileRoller.desktop" ];
            "application/rar" = [ "org.gnome.FileRoller.desktop" ];
            "application/7z" = [ "org.gnome.FileRoller.desktop" ];
            "application/*tar" = [ "org.gnome.FileRoller.desktop" ];
          };
        };
      };
    };
  };
}
