# Interface Domain Module
# Complete UI experience (system + desktop)
# Consolidates: desktop environment, themes, terminal, compositor

{
  lib,
  pkgs,
  config,
  inputs,
  ...
}:
{
  config = {
    system.nixos.tags = [ "interface-domain-v0.3" ];

    # === STYLIX SYSTEM-WIDE THEMING ===
    stylix = {
      enable = true;

      # Use gruvbox dark theme
      base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-medium.yaml";

      image = ./asset/forest.jpg;

      fonts = {
        monospace = {
          package = pkgs.nerd-fonts.sauce-code-pro;
          name = "SauceCodePro Nerd Font Mono";
        };
        sansSerif = {
          package = pkgs.liberation_ttf; # Arimo is part of liberation fonts
          name = "Arimo";
          # name = "Noto Sans";  # Alternative
        };
        serif = {
          package = pkgs.liberation_ttf; # Tinos is part of liberation fonts
          name = "Tinos";
          # name = "Noto Serif";  # Alternative
        };
        emoji = {
          package = pkgs.noto-fonts-emoji;
          name = "Noto Color Emoji";
        };
        sizes = {
          applications = 12;
          desktop = 11;
          popups = 11;
          terminal = 16;
        };
      };

      cursor = {
        package = pkgs.bibata-cursors;
        name = "Bibata-Modern-Ice";
        size = 24;
      };

      opacity = {
        applications = 1.0;
        desktop = 1.0;
        popups = 1.0;
        terminal = 0.9;
      };

      polarity = "dark";
    };

    programs.hyprland = {
      enable = true;
      withUWSM = true;
      package = inputs.hyprland.packages.${pkgs.system}.hyprland;
    };

    programs.uwsm = {
      enable = true;
    };

    xdg.portal = {
      enable = true;
      wlr.enable = true;
      xdgOpenUsePortal = true;
      extraPortals = with pkgs; [
        xdg-desktop-portal
        xdg-desktop-portal-gtk
      ];
      config = {
        common = {
          default = [
            "gtk"
            "hyprland"
          ];
          "org.freedesktop.portal.OpenURI" = [
            "gtk"
            "hyprland"
          ];
        };
      };
    };

    environment.systemPackages = with pkgs; [
      wlr-randr # Wayland equivalent to xrandr
    ];

    # === HOME MANAGER CONFIGURATION FOR INTERFACE DOMAIN ===
    home-manager.users.sinity = {

      # === DESKTOP ENVIRONMENT (from home/desktop) ===
      home = {
        packages = with pkgs; [
          # Pyprland for advanced scratchpad management
          pyprland
          # Screenshot and screen recording utilities
          grim # Screenshot utility
          slurp # Region selection tool
          grimblast # Screenshot tool using grim and slurp
          wl-screenrec # Screen recording

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

      wayland.windowManager.hyprland = {
        enable = true;
        xwayland.enable = true;
        systemd.enable = false;

        # Hyprland plugins
        plugins = [ ];

        settings = {
          exec-once = [
            # UWSM handles most of the environment and service management
            "uwsm finalize"
          ];

          # Monitor configuration for 4K HDR display
          monitor = [
            "DP-3,3840x2160@119.999001,0x0,1,bitdepth,10,cm,hdr,sdrbrightness,1.4,sdrsaturation,1.0"
          ];

          input = {
            kb_layout = "pl";
            repeat_rate = 40;
            repeat_delay = 400;
            mouse_refocus = true; # Refocus when mouse moves
            sensitivity = 0;
            accel_profile = "flat";
            force_no_accel = 0;
            scroll_factor = 1;
            follow_mouse = 1;
          };

          general = {
            border_size = 3;
            gaps_in = 10;
            gaps_out = 20;
            layout = "dwindle"; # Restored to original dwindle layout
            resize_on_border = true;
          };

          dwindle = {
            force_split = 0;
            special_scale_factor = 1.0;
            split_width_multiplier = 1.0;
            use_active_for_splits = true;
            pseudotile = "yes";
            preserve_split = "yes";
          };

          misc = {
            disable_hyprland_logo = true;
            vrr = 2; # Fullscreen only VRR for better performance
            mouse_move_enables_dpms = true;
            key_press_enables_dpms = true;
            always_follow_on_dnd = true;
            focus_on_activate = true;
            middle_click_paste = true; # Enable middle-click paste
            enable_swallow = true; # Terminal window swallowing
            swallow_regex = "^(kitty)$"; # Your terminal
          };

          debug = {
            disable_logs = false;
            disable_time = false;
            enable_stdout_logs = true;
          };

          decoration = {
            rounding = 0;
            active_opacity = 1.0;
            inactive_opacity = 0.7; # More dramatic focus hierarchy
            dim_inactive = true;
            dim_strength = 0.3; # Stronger dimming for better focus

            blur = {
              enabled = true;
              size = 8; # Increased for RTX 3080
              passes = 3; # Higher quality blur
              new_optimizations = true;
              vibrancy = 0.15; # Subtle color enhancement
              vibrancy_darkness = 0.2;
            };

            shadow = {
              enabled = true;
              range = 20;
              render_power = 3;
              offset = "0 8";
            };
          };

          animations = {
            enabled = false;
          };

          bind = [
            # === CORE FUNCTIONALITY ===
            "SUPER, Return, exec, kitty"
            "SUPER, Q, killactive"
            "SUPER, F, fullscreen, 0"
            "SUPER, D, exec, tofi-drun --drun-launch=true"
            "SUPER, Escape, exec, hyprlock"

            # === WINDOW MANAGEMENT ===
            # Focus movement (vim-style) - works for all layouts
            "SUPER, H, movefocus, l"
            "SUPER, J, movefocus, d"
            "SUPER, K, movefocus, u"
            "SUPER, L, movefocus, r"

            # Window movement - works for all layouts
            "SUPER SHIFT, H, movewindow, l"
            "SUPER SHIFT, L, movewindow, r"
            "SUPER SHIFT, K, movewindow, u"
            "SUPER SHIFT, J, movewindow, d"

            # Master layout control (defined in extraConfig for more options)

            # Floating
            "SUPER, Space, togglefloating"
            "SUPER, Space, centerwindow"

            # === WORKSPACES ===
            "SUPER, 1, workspace, 1"
            "SUPER, 2, workspace, 2"
            "SUPER, 3, workspace, 3"
            "SUPER, 4, workspace, 4"
            "SUPER, 5, workspace, 5"
            # Workspaces 6-9 removed as requested

            # Move to workspace
            "SUPER SHIFT, 1, movetoworkspace, 1"
            "SUPER SHIFT, 2, movetoworkspace, 2"
            "SUPER SHIFT, 3, movetoworkspace, 3"
            "SUPER SHIFT, 4, movetoworkspace, 4"
            "SUPER SHIFT, 5, movetoworkspace, 5"

            # === SPECIAL WORKSPACES ===
            # Terminal scratchpad
            "SUPER, grave, exec, pypr toggle term"

            # Music scratchpad
            "SUPER, S, exec, pypr toggle spotify"

            # Pypr scratchpad notes (replaces native special workspace)
            "SUPER, N, exec, pypr toggle notes"

            # === UTILITIES ===
            "SUPER, V, exec, kitty --class clipse -e clipse"
            ", Print, exec, grimblast --notify --freeze copysave area /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
            "SUPER, Print, exec, grimblast --notify --cursor copysave output /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
            ", F8, exec, log-to-knowledgebase"

            "SUPER SHIFT, P, pin" # Picture-in-Picture: pin window on top of all workspaces

            # === MEDIA KEYS WITH VISUAL FEEDBACK ===
            ",XF86AudioMute, exec, pamixer -t && notify-send -t 800 '🔇 Audio' 'Muted: '$(pamixer --get-mute)"
            ",XF86AudioPlay, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
            ",XF86AudioNext, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
            ",XF86AudioPrev, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
            ",XF86AudioRaiseVolume, exec, pamixer -i 2 && notify-send -t 800 '🔊 Volume' '$(pamixer --get-volume)%'"
            ",XF86AudioLowerVolume, exec, pamixer -d 2 && notify-send -t 800 '🔉 Volume' '$(pamixer --get-volume)%'"

            # === QUICK RESIZE (for 4K) ===
            "SUPER CTRL, H, resizeactive, -80 0"
            "SUPER CTRL, L, resizeactive, 80 0"
            "SUPER CTRL, K, resizeactive, 0 -80"
            "SUPER CTRL, J, resizeactive, 0 80"

            # === MOVE ACTIVE WINDOW ===
            "SUPER ALT, H, moveactive, -80 0"
            "SUPER ALT, L, moveactive, 80 0"
            "SUPER ALT, K, moveactive, 0 -80"
            "SUPER ALT, J, moveactive, 0 80"

            # === DWINDLE LAYOUT MANAGEMENT ===
            "SUPER, P, pseudo" # Toggle pseudo tiling
            "SUPER, Y, togglesplit" # Toggle split direction

          ];

          bindl = [
            ",XF86MonBrightnessUp, exec, brightnessctl set 5%+"
            ",XF86MonBrightnessDown, exec, brightnessctl set 5%-"
            "SUPER, XF86MonBrightnessUp, exec, brightnessctl set 100%+"
            "SUPER, XF86MonBrightnessDown, exec, brightnessctl set 100%-"
          ];

          binde = [ ];

          bindm = [
            "SUPER, mouse:272, movewindow"
            "SUPER, mouse:273, resizewindow"
            "SUPER ALT, mouse:272, resizewindow" # Alternative resize with ALT
          ];

          windowrule = [
            # === CORE RULES ===

            # Media should not dim screen
            "idleinhibit focus,class:^(mpv)$"
            "idleinhibit fullscreen,class:^(firefox)$"
            "idleinhibit fullscreen,class:^(google-chrome)$"

            # === FLOATING WINDOWS ===
            # Dialogs and popups
            "float,title:^(Open File)$"
            "float,title:^(Save As)$"
            "float,class:^(pavucontrol)$"
            "float,class:^(nm-connection-editor)$"

            # Center floating windows
            "center,floating:1"

            # Smart Picture-in-Picture positioning
            "float,title:^(Picture-in-Picture)$"
            "pin,title:^(Picture-in-Picture)$"
            "size 480 270,title:^(Picture-in-Picture)$"
            "move 100%-500 50,title:^(Picture-in-Picture)$" # Smart corner positioning

            # Music apps to special:music
            "workspace special:music,class:^(Spotify)$"
            "workspace special:music,class:^(spotify)$" # Sometimes lowercase
            "workspace special:music,class:^(music)$" # Our kitty music instances
            "workspace special:music,title:^(ncspot)$"
            "workspace special:music,class:^(pavucontrol)$"
            "workspace special:music,class:^(pwvucontrol)$"
            "workspace special:music,class:^(blueman-manager)$"

            # Audio and bluetooth opacity - pypr handles positioning
            "opacity 0.8 0.8,class:^(pwvucontrol)$"
            "opacity 0.8 0.8,class:^(blueman-manager)$"

            # === CLIPBOARD MANAGER ===
            "float,class:(clipse)"
            "center,class:(clipse)"
            "size 2000 1000,class:(clipse)"

            # === GAMING OPTIMIZATIONS ===
            # Steam games get immediate mode and dedicated workspace
            "immediate,class:^(steam_app_.*)$"
            "fullscreen,class:^(steam_app_.*)$"
            "workspace 5,class:^(steam_app_.*)$" # Changed from 9 to 5

            # === UTILITIES ===
            # File picker should float
            "float,class:^(xdg-desktop-portal-gtk)$"
            "size 1200 800,class:^(xdg-desktop-portal-gtk)$"

            # Image viewers
            "float,class:^(imv)$"
            "center,class:^(imv)$"
          ];
        };

        extraConfig = '''';
      };

      # === PYPRLAND CONFIGURATION ===
      xdg.configFile."hypr/pyprland.toml".text = builtins.readFile ../pyprland.toml;

      # PYPRLAND systemd service
      systemd.user.services.pyprland = {
        Unit = {
          Description = "Pyprland daemon for advanced scratchpad management";
          After = [ "graphical-session.target" ];
          PartOf = [ "graphical-session.target" ];
          Wants = [ "graphical-session.target" ];
        };
        Service = {
          Type = "simple";
          ExecStart = "${pkgs.pyprland}/bin/pypr";
          ExecReload = "${pkgs.coreutils}/bin/kill -HUP $MAINPID";
          Restart = "on-failure";
          RestartSec = 2;
          KillMode = "mixed";
          TimeoutStopSec = 5;
          # Clean up any stale socket files in the hypr runtime directory
          ExecStartPre = "${pkgs.bash}/bin/bash -c 'rm -f /run/user/$UID/hypr/*/.pyprland.sock'";
          # Ensure runtime directory exists
          RuntimeDirectory = "pyprland";
          RuntimeDirectoryMode = "0755";
        };
        Install = {
          WantedBy = [ "graphical-session.target" ];
        };
      };

      # Environment variables for proper Wayland/Hyprland operation
      home.sessionVariables = {
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

      # === HYPRLOCK (from home/desktop/hyprland/hyprlock.nix) ===
      xdg.configFile."hypr/hyprlock.conf".text = ''
        # BACKGROUND
        background {
          monitor =
          path = ${./asset/forest.jpg}
          blur_passes = 1
          contrast = 0.8916
          brightness = 0.8172
          vibrancy = 0.1696
          vibrancy_darkness = 0.0
        }

        # GENERAL
        general {
          hide_cursor = true
          no_fade_in = false
          grace = 0
          disable_loading_bar = false
        }

        # Time
        label {
          monitor =
          text = cmd[update:1000] echo "$(date +"%k:%M")"
          color = rgba(235, 219, 178, .9)
          font_size = 111
          font_family = JetBrainsMono NF Bold
          position = 0, 270
          halign = center
          valign = center
        }

        # Day
        label {
          monitor =
          text = cmd[update:1000] echo "- $(date +"%A, %B %d") -"
          color = rgba(235, 219, 178, .9)
          font_size = 20
          font_family = FiraCode Nerd Font
          position = 0, 160
          halign = center
          valign = center
        }

        # USER-BOX
        shape {
          monitor =
          size = 350, 50
          color = rgba(225, 225, 225, .2)
          rounding = 15
          border_size = 0
          border_color = rgba(255, 255, 255, 0)
          rotate = 0

          position = 0, -230
          halign = center
          valign = center
        }

        # USER
        label {
          monitor =
          text =   $USER
          color = rgba(235, 219, 178, .9)
          font_size = 16
          font_family = FiraCode Nerd Font
          position = 0, -230
          halign = center
          valign = center
        }

        # INPUT FIELD
        input-field {
          monitor =
          size = 350, 50
          outline_thickness = 0
          rounding = 15
          dots_size = 0.25 # Scale of input-field height, 0.2 - 0.8
          dots_spacing = 0.4 # Scale of dots' absolute size, 0.0 - 1.0
          dots_center = true
          outer_color = rgba(255, 255, 255, 0)
          inner_color = rgba(225, 225, 225, 0.2)
          color = rgba(235, 219, 178, .9)
          font_color = rgba(235, 219, 178, .9)
          fade_on_empty = false
          placeholder_text = <i><span foreground="##ebdbb2e5">Enter Password</span></i>
          hide_input = false
          position = 0, -300
          halign = center
          valign = center
        }
      '';

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

        style = builtins.readFile ./asset/waybar-style.css;
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
          # allow_remote_control and listen_on are now handled by Sinex auto-configuration
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

        style = builtins.readFile ./asset/swaync-style.css;
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
