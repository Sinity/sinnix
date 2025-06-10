# Hyprland Configuration
# Window manager configuration, pyprland, hyprlock, and hyprland-specific utilities

{
  pkgs,
  config,
  ...
}:
{
  config = {
    home-manager.users.sinity = {
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
            ",XF86AudioNext, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \\\"Unknown\\\")'"
            ",XF86AudioPrev, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \\\"Unknown\\\")'"
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
      xdg.configFile."hypr/pyprland.toml".text = builtins.readFile ../asset/pyprland.toml;

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

      # === HYPRLOCK (from home/desktop/hyprland/hyprlock.nix) ===
      xdg.configFile."hypr/hyprlock.conf".text = ''
        # BACKGROUND
        background {
          monitor =
          path = ${../asset/forest.jpg}
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

      home.packages = with pkgs; [
        # Pyprland for advanced scratchpad management
        pyprland
        # Screenshot and screen recording utilities
        grim # Screenshot utility
        slurp # Region selection tool
        grimblast # Screenshot tool using grim and slurp
        wl-screenrec # Screen recording
      ];
    };
  };
}
