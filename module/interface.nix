# Interface Domain Module
# Complete UI experience (system + desktop)
# Consolidates: desktop environment, themes, terminal, compositor

{ lib, pkgs, ... }:
{
  config = {
    system.nixos.tags = [ "interface-domain-v0.3" ];

    programs.hyprland.enable = true;

    xdg.portal = {
      enable = true;
      wlr.enable = true;
      xdgOpenUsePortal = true;
      extraPortals = with pkgs; [
        xdg-desktop-portal
        xdg-desktop-portal-hyprland
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

    fonts = {
      fontDir.enable = true;
      packages =
        with pkgs;
        [
          noto-fonts
          noto-fonts-extra
          noto-fonts-emoji

          source-code-pro
          source-sans-pro
          source-serif-pro

          source-han-code-jp
          source-han-mono
          source-han-sans
          source-han-serif

          font-awesome

          hermit
          roboto
          roboto-mono
          roboto-slab
        ]
        ++ builtins.filter lib.attrsets.isDerivation (builtins.attrValues pkgs.nerd-fonts);

      fontconfig = {
        enable = true;
        defaultFonts = {
          monospace = [ "SauceCodePro Nerd Font Mono" ];
          sansSerif = [ "Arimo" ];
          serif = [ "Tinos" ];
          emoji = [ "Noto Color Emoji" ];
        };
      };
    };

    # === HOME MANAGER CONFIGURATION FOR INTERFACE DOMAIN ===
    home-manager.users.sinity = {

      # === DESKTOP ENVIRONMENT (from home/desktop) ===
      home = {
        packages = with pkgs; [
          # Screenshot and screen recording utilities
          grim # Screenshot utility
          slurp # Region selection tool
          grimblast # Screenshot tool using grim and slurp
          wl-screenrec # Screen recording

          # Clipboard management
          wl-clip-persist # Keep clipboard content after application closes
          wl-clipboard # Wayland clipboard utilities
          cliphist # Clipboard history manager
          clipboard-jh # Cut, copy, and paste anything in your terminal

          # Notification center from swaync/default.nix
          swaynotificationcenter

          # Color and appearance
          swaybg # Wallpaper utility
          hyprpicker # Color picker
          wl-gammactl # Adjust gamma
          wlsunset # Night light/blue light filter
          redshift # Adjust color temperature (X11/Wayland)

          # GTK Theming Packages (from packages.nix)
          (gruvbox-gtk-theme.override { colorVariants = [ "dark" ]; })
          (papirus-icon-theme.override { color = "black"; })
          bibata-cursors

          # Fonts (from packages.nix)
          # fira-code # Monospaced font with programming ligatures
          hack-font # Patched font Hack from nerd fonts library

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

          # Additional desktop apps from desktop-apps.nix
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

          # Additional packages from packages.nix
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

      # === GTK THEME CONFIGURATION (from desktop/themes.nix) ===
      gtk = {
        enable = true;
        theme = {
          name = "Gruvbox-Dark";
          package = pkgs.gruvbox-gtk-theme.override { colorVariants = [ "dark" ]; };
        };
        iconTheme = {
          name = "Papirus-Dark";
          package = pkgs.papirus-icon-theme.override { color = "black"; };
        };
        cursorTheme = {
          name = "Bibata-Modern-Ice";
          size = 24;
          package = pkgs.bibata-cursors;
        };

        gtk3.extraConfig = {
          gtk-icon-theme-name = "Papirus-Dark";
          gtk-theme-name = "Gruvbox-Dark";
          gtk-cursor-theme-name = "Bibata-Modern-Ice";
        };

        gtk4.extraConfig = {
          gtk-icon-theme-name = "Papirus-Dark";
          gtk-theme-name = "Gruvbox-Dark";
          gtk-cursor-theme-name = "Bibata-Modern-Ice";
        };
      };

      home.file.".icons/default/index.theme".text = ''
        [Icon Theme]
        Inherits=Bibata-Modern-Ice
      '';

      systemd.user.targets.hyprland-session.Unit.Wants = [ "xdg-desktop-autostart.target" ];

      wayland.windowManager.hyprland = {
        enable = true;
        xwayland.enable = true;
        systemd.enable = true;

        settings = {
          exec-once = [
            "systemctl --user import-environment &"
            "hash dbus-update-activation-environment 2>/dev/null &"
            "dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_SESSION_DESKTOP &"
            "nm-applet &"
            "wl-clip-persist --clipboard both"
            "swaybg -m fill -i $(find ~/pic/wallpaper/ -maxdepth 1 -type f) &"
            "hyprctl setcursor Bibata-Modern-Ice 24 &"
            "poweralertd &"
            "waybar &"
            "swaync &"
            "wl-paste --watch cliphist store -max-items 99999 -max-dedupe-search 20 &"
            "systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP &"
            "systemctl --user restart pipewire &"
            "systemctl --user restart xdg-desktop-portal.service &"
            "systemctl --user restart xdg-desktop-portal-hyprland.service &"
          ];

          input = {
            kb_layout = "pl";
            kb_options = "";
            numlock_by_default = true;
            repeat_rate = 40;
            repeat_delay = 400;
            sensitivity = 0;
            accel_profile = "flat";
            force_no_accel = 0;
            scroll_factor = 1;
            emulate_discrete_scroll = 1;
            follow_mouse = 1;
            mouse_refocus = false;
            float_switch_override_focus = 2;
            special_fallthrough = true;
          };

          general = {
            border_size = 3;
            gaps_in = 10;
            gaps_out = 20;
            "col.inactive_border" = "0x00000000";
            "col.active_border" = "rgb(98971a) rgb(cc241d) 45deg";
            layout = "dwindle";
            resize_on_border = true;
          };

          misc = {
            disable_hyprland_logo = false;
            vrr = 1;
            mouse_move_enables_dpms = true;
            key_press_enables_dpms = true;
            always_follow_on_dnd = true;
            layers_hog_keyboard_focus = true;
            animate_manual_resizes = false;
            animate_mouse_windowdragging = false;
            disable_autoreload = true;
            focus_on_activate = true;
            new_window_takes_over_fullscreen = 2;
            middle_click_paste = true;
          };

          dwindle = {
            force_split = 0;
            special_scale_factor = 1.0;
            split_width_multiplier = 1.0;
            use_active_for_splits = true;
            pseudotile = "yes";
            preserve_split = "yes";
          };

          master = {
            new_status = "master";
            special_scale_factor = 1;
          };

          group = {
            insert_after_current = true;
            focus_removed_window = true;
            groupbar = {
              enabled = true;
              gradients = true;
              height = 14;
              render_titles = true;
              scrolling = true;
            };
          };

          debug = {
            disable_logs = false;
            disable_time = false;
            enable_stdout_logs = true;
          };

          decoration = {
            rounding = 0;
            active_opacity = 1.0;
            inactive_opacity = 0.9;
            fullscreen_opacity = 1.0;
            blur = {
              enabled = true;
              size = 4;
              passes = 2;
              contrast = 1.4;
              brightness = 1;
              vibrancy = 0.5;
              special = true;
            };
          };

          animations = {
            enabled = true;
            bezier = [
              "fluent_decel, 0, 0.2, 0.4, 1"
              "easeOutCirc, 0, 0.55, 0.45, 1"
              "easeOutCubic, 0.33, 1, 0.68, 1"
              "easeinoutsine, 0.37, 0, 0.63, 1"
            ];
            animation = [
              "windowsIn, 1, 3, easeOutCubic, popin 30%"
              "windowsOut, 1, 3, fluent_decel, popin 70%"
              "windowsMove, 1, 2, easeinoutsine, slide"
              "fadeIn, 1, 3, easeOutCubic"
              "fadeOut, 1, 2, easeOutCubic"
              "fadeSwitch, 0, 1, easeOutCirc"
              "fadeShadow, 1, 10, easeOutCirc"
              "fadeDim, 1, 4, fluent_decel"
              "border, 1, 2.7, easeOutCirc"
              "borderangle, 1, 30, fluent_decel, once"
              "workspaces, 1, 4, easeOutCubic, fade"
            ];
          };

          bind = [
            "SUPER, F1, exec, show-keybinds"
            "SUPER, Return, exec, kitty"
            "ALT, Return, exec, kitty --title float_kitty"
            "SUPER SHIFT, Return, exec, kitty --start-as=fullscreen -o 'font_size=16'"
            "SUPER, Q, killactive,"
            "SUPER, F, fullscreen, 0"
            "SUPER SHIFT, F, fullscreen, 1"
            "SUPER, Space, togglefloating,"
            "SUPER, Space, centerwindow,"
            "SUPER, Space, resizeactive, exact 950 600"
            "SUPER, D, exec, rofi -show drun || pkill rofi"
            "SUPER SHIFT, S, exec, hyprctl dispatch exec '[workspace 5 silent] SoundWireServer'"
            "SUPER, Escape, exec, swaylock"
            "ALT, Escape, exec, hyprlock"
            "SUPER, P, pseudo,"
            "SUPER, Y, togglesplit,"
            "SUPER, T, exec, toggle_opacity"
            "SUPER, E, exec, nautilus"
            "SUPER SHIFT, B, exec, toggle_waybar"
            "SUPER, C ,exec, hyprpicker -a"
            "SUPER, N, exec, swaync-client -t -sw"
            "SUPER SHIFT, W, exec, vm-start"
            "SUPER, Print, exec, grimblast --notify --cursor copysave output /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
            ", Print, exec, grimblast --notify --freeze copysave area /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
            ", F8, exec, log-to-knowledgebase"
            "SUPER, H, movefocus, l"
            "SUPER, J, movefocus, d"
            "SUPER, K, movefocus, u"
            "SUPER, L, movefocus, r"
            "SUPER, 1, workspace, 1"
            "SUPER, 2, workspace, 2"
            "SUPER, 3, workspace, 3"
            "SUPER, 4, workspace, 4"
            "SUPER, 5, workspace, 5"
            "SUPER, 6, workspace, 6"
            "SUPER, 7, workspace, 7"
            "SUPER, 8, workspace, 8"
            "SUPER, 9, workspace, 9"
            "SUPER, 0, workspace, 10"
            "SUPER SHIFT, 1, movetoworkspacesilent, 1"
            "SUPER SHIFT, 2, movetoworkspacesilent, 2"
            "SUPER SHIFT, 3, movetoworkspacesilent, 3"
            "SUPER SHIFT, 4, movetoworkspacesilent, 4"
            "SUPER SHIFT, 5, movetoworkspacesilent, 5"
            "SUPER SHIFT, 6, movetoworkspacesilent, 6"
            "SUPER SHIFT, 7, movetoworkspacesilent, 7"
            "SUPER SHIFT, 8, movetoworkspacesilent, 8"
            "SUPER SHIFT, 9, movetoworkspacesilent, 9"
            "SUPER SHIFT, 0, movetoworkspacesilent, 10"
            "SUPER CTRL, c, movetoworkspace, empty"
            "SUPER SHIFT, H, movewindow, l"
            "SUPER SHIFT, L, movewindow, r"
            "SUPER SHIFT, K, movewindow, u"
            "SUPER SHIFT, J, movewindow, d"
            "SUPER CTRL, H, resizeactive, -80 0"
            "SUPER CTRL, L, resizeactive, 80 0"
            "SUPER CTRL, K, resizeactive, 0 -80"
            "SUPER CTRL, J, resizeactive, 0 80"
            "SUPER ALT, H, moveactive,  -80 0"
            "SUPER ALT, L, moveactive, 80 0"
            "SUPER ALT, K, moveactive, 0 -80"
            "SUPER ALT, J, moveactive, 0 80"
            ",XF86AudioMute, exec, pamixer -t"
            ",XF86AudioPlay, exec, playerctl play-pause"
            ",XF86AudioNext, exec, playerctl next"
            ",XF86AudioPrev, exec, playerctl previous"
            ",XF86AudioStop, exec, playerctl stop"
            ",XF86AudioRaiseVolume, exec, pamixer -i 2"
            ",XF86AudioLowerVolume, exec, pamixer -d 2"
            "SUPER, mouse_down, workspace, e-1"
            "SUPER, mouse_up, workspace, e+1"
            "SUPER, V, exec, cliphist list | rofi -dmenu -theme-str 'window {width: 50%;}' | cliphist decode | wl-copy"
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
          ];

          windowrule = [
            "float,class:qView"
            "center,class:qView"
            "size 1200 725,class:qView"
            "float,class:imv"
            "center,class:imv"
            "size 1200 725,class:imv"
            "tile,class:Aseprite"
            "float,title:^(float_kitty)$"
            "center,title:^(float_kitty)$"
            "size 950 600,title:^(float_kitty)$"
            "float,class:audacious"
            "pin,class:rofi"
            "tile,class:neovide"
            "idleinhibit focus,class:mpv"
            "float,class:udiskie"
            "float,title:^(Transmission)$"
            "float,title:^(Volume Control)$"
            "float,title:^(Firefox — Sharing Indicator)$"
            "move 0 0,title:^(Firefox — Sharing Indicator)$"
            "size 700 450,title:^(Volume Control)$"
            "move 40 55%,title:^(Volume Control)$"
            "float,title:^(Picture-in-Picture)$"
            "opacity 1.0 override 1.0 override,title:^(Picture-in-Picture)$"
            "pin,title:^(Picture-in-Picture)$"
            "opacity 1.0 override 1.0 override,title:^(.*imv.*)$"
            "opacity 1.0 override 1.0 override,title:^(.*mpv.*)$"
            "opacity 1.0 override 1.0 override,class:(Aseprite)"
            "opacity 1.0 override 1.0 override,class:(Unity)"
            "opacity 1.0 override 1.0 override,class:(google-chrome)"
            "opacity 1.0 override 1.0 override,class:(evince)"
            "workspace 1,class:^(zen)$"
            "workspace 4,class:^(discord)$"
            "workspace 4,class:^(Gimp-2.10)$"
            "workspace 4,class:^(Aseprite)$"
            "workspace 5,class:^(Audacious)$"
            "workspace 5,class:^(Spotify)$"
            "idleinhibit focus,class:^(mpv)$"
            "idleinhibit fullscreen,class:^(firefox)$"
            "float,class:^(zenity)$"
            "center,class:^(zenity)$"
            "size 850 500,class:^(zenity)$"
            "float,class:^(org.gnome.FileRoller)$"
            "center,class:^(org.gnome.FileRoller)$"
            "size 850 500,class:^(org.gnome.FileRoller)$"
            "size 850 500,title:^(File Upload)$"
            "float,class:^(pavucontrol)$"
            "float,class:^(SoundWireServer)$"
            "float,class:^(.sameboy-wrapped)$"
            "float,class:^(file_progress)$"
            "float,class:^(confirm)$"
            "float,class:^(dialog)$"
            "float,class:^(download)$"
            "float,class:^(notification)$"
            "float,class:^(error)$"
            "float,class:^(confirmreset)$"
            "float,title:^(Open File)$"
            "float,title:^(File Upload)$"
            "float,title:^(branchdialog)$"
            "float,title:^(Confirm to replace files)$"
            "float,title:^(File Operation Progress)$"
            "opacity 0.0 override,class:^(xwaylandvideobridge)$"
            "noanim,class:^(xwaylandvideobridge)$"
            "noinitialfocus,class:^(xwaylandvideobridge)$"
            "maxsize 1 1,class:^(xwaylandvideobridge)$"
            "noblur,class:^(xwaylandvideobridge)$"
            "noanim,class:^(ueberzug)$"
          ];
        };

        extraConfig = "\n      monitor=DP-3,3840x2160@119.999001,0x0,1, bitdepth, 10, cm, hdr, sdrbrightness, 1.4, sdrsaturation, 1.0\n    ";
      };

      # Environment variables for proper Wayland/Hyprland operation
      home.sessionVariables = {
        INTERFACE_DOMAIN = "v0.3";

        # Default applications from environment.nix
        BROWSER = "google-chrome-stable";
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
            format-icons = {
              "1" = "I";
              "2" = "II";
              "3" = "III";
              "4" = "IV";
              "5" = "V";
              "6" = "VI";
              "7" = "VII";
              "8" = "VIII";
              "9" = "IX";
              sort-by-number = true;
            };
            persistent-workspaces = {
              "1" = [ ];
              "2" = [ ];
              "3" = [ ];
              "4" = [ ];
              "5" = [ ];
              "6" = [ ];
              "7" = [ ];
              "8" = [ ];
              "9" = [ ];
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
            on-click = "rofi -show drun";
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
        font = {
          name = "FiraCode Nerd Font";
          size = 16;
        };
        settings = {
          background_opacity = "0.90";
          window_padding_width = 10;
          scrollback_lines = 10000;
          enable_audio_bell = "no";
          mouse_hide_wait = 60;
          wheel_scroll_multiplier = 0.5;
          touch_scroll_multiplier = 0.5;
          cursor_trail = 3;
          confirm_os_window_close = 0;
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
          # Gruvbox Dark theme for Kitty
          # Based on https://github.com/morhetz/gruvbox

          # Basic colors
          foreground            #ebdbb2
          background            #282828
          selection_foreground  #928374
          selection_background  #ebdbb2

          # Cursor colors
          cursor                #bdae93
          cursor_text_color     #665c54

          # URL underline color when hovering
          url_color             #83a598

          # Window border colors
          active_border_color   #d3869b
          inactive_border_color #665c54

          # Tab bar colors
          active_tab_foreground #fbf1c7
          active_tab_background #7c6f64
          inactive_tab_foreground #fbf1c7
          inactive_tab_background #3c3836

          # Normal colors
          color0                #282828
          color1                #cc241d
          color2                #98971a
          color3                #d79921
          color4                #458588
          color5                #b16286
          color6                #689d6a
          color7                #a89984

          # Bright colors
          color8                #928374
          color9                #fb4934
          color10               #b8bb26
          color11               #fabd2f
          color12               #83a598
          color13               #d3869b
          color14               #8ec07c
          color15               #ebdbb2

          # Extended colors
          color16               #fe8019
          color17               #d65d0e
          color18               #3c3836
          color19               #504945
          color20               #bdae93
          color21               #ebdbb2

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

      # === ROFI CONFIGURATION ===
      programs.rofi = {
        enable = true;
        package = pkgs.rofi-wayland;
        terminal = "\${pkgs.kitty}/bin/kitty";
        theme = "gruvbox-dark";
        font = "JetBrainsMono Nerd Font 12";
        extraConfig = {
          disable-history = false;
          display-Network = " 󰤨  Network";
          display-drun = "   Apps ";
          display-run = "   Run ";
          display-window = " 﩯  Window";
          drun-display-format = "{icon} {name}";
          hide-scrollbar = true;
          icon-theme = "Papirus-Dark";
          location = 0;
          modi = "run,drun,window";
          show-icons = true;
          sidebar-mode = true;
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
            "text/html" = [ "google-chrome.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome.desktop" ];
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
            "text/html" = [ "google-chrome.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome.desktop" ];
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
