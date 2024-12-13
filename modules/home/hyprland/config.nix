{ ... }: 
{
  wayland.windowManager.hyprland = {
    settings = {
      exec-once = [
        "systemctl --user import-environment &"
        "hash dbus-update-activation-environment 2>/dev/null &"
        "dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP &"
        "nm-applet &"
        "wl-clip-persist --clipboard both"
        "swaybg -m fill -i $(find ~/pic/wallpaper/ -maxdepth 1 -type f) &"
        "hyprctl setcursor Bibata-Modern-Ice 24 &"
        "poweralertd &"
        "waybar &"
        "swaync &"
        "wl-paste --watch cliphist store -max-items 99999 -max-dedupe-search 20 &"
        # "wl-paste --primary --watch ???" # TODO: set this up when I figure out where to store these
        "hyprlock"

        ## App auto start
        "[workspace 1 silent] floorp"
        "[workspace 2 silent] kitty"
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
      	# focus_on_close = 0;
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
	      vrr = 2;
	      mouse_move_enables_dpms = true;
	      key_press_enables_dpms = true;
        always_follow_on_dnd = true;
        layers_hog_keyboard_focus = true;
        animate_manual_resizes = false;
	      animate_mouse_windowdragging = false;
        disable_autoreload = true;
        enable_swallow = true;
      	# swallow_regex = "^(kitty(?!.*ranger))$";
        focus_on_activate = true;
	      # render_ahead_of_time = true;
	      # render_ahead_safezone = 2;
        new_window_takes_over_fullscreen = 2;
        middle_click_paste = true;
      };

      dwindle = {
        # no_gaps_when_only = true;
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
        # no_gaps_when_only = false;
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
        active_opacity = 1.00;
        inactive_opacity = 0.90;
        fullscreen_opacity = 1.00;

        # drop_shadow = true;
        # shadow_ignore_window = true;
        # shadow_offset = "0 2";
        # shadow_range = 20;
        # shadow_render_power = 3;
        # "col.shadow" = "rgba(00000055)";

        blur = {
          enabled = true;
          size = 4;
          passes = 2;
          contrast = 1.400;
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
          # Windows
          "windowsIn, 1, 3, easeOutCubic, popin 30%" # window open
          "windowsOut, 1, 3, fluent_decel, popin 70%" # window close
          "windowsMove, 1, 2, easeinoutsine, slide" # window move

          # Fade
          "fadeIn, 1, 3, easeOutCubic" # fade in (open) -> layers and windows
          "fadeOut, 1, 2, easeOutCubic" # fade out (close) -> layers and windows
          "fadeSwitch, 0, 1, easeOutCirc" # fade on changing activewindow
          "fadeShadow, 1, 10, easeOutCirc" # shadow fade on changing activewindow
          "fadeDim, 1, 4, fluent_decel" # dimming fade of inactive windows
          "border, 1, 2.7, easeOutCirc" # border color switch speed
          "borderangle, 1, 30, fluent_decel, once" # once (default), loop
          "workspaces, 1, 4, easeOutCubic, fade" # slide, fade, slidefade...
        ];
      };

      bind = [
        "SUPER, F1, exec, show-keybinds" # keybinds cheatsheet 
        "SUPER, Return, exec, kitty"
        "ALT, Return, exec, kitty --title float_kitty"
        "SUPER SHIFT, Return, exec, kitty --start-as=fullscreen -o 'font_size=16'"
        "SUPER, B, exec, hyprctl dispatch exec '[workspace 1 silent] floorp'"
        "SUPER, Q, killactive,"
        "SUPER, F, fullscreen, 0"
        "SUPER SHIFT, F, fullscreen, 1"
        "SUPER, Space, togglefloating,"
        "SUPER, Space, centerwindow,"
        "SUPER, Space, resizeactive, exact 950 600"
        "SUPER, D, exec, rofi -show drun || pkill rofi"
        "SUPER SHIFT, D, exec, hyprctl dispatch exec '[workspace 4 silent] discord --enable-features=UseOzonePlatform --ozone-platform=wayland'"
        "SUPER SHIFT, S, exec, hyprctl dispatch exec '[workspace 5 silent] SoundWireServer'"
        "SUPER, Escape, exec, swaylock"
        "ALT, Escape, exec, hyprlock"
        "SUPER SHIFT, Escape, exec, power-menu"
        "SUPER, P, pseudo,"
        "SUPER, Y, togglesplit,"
        "SUPER, T, exec, toggle_oppacity"
        "SUPER, E, exec, nautilus"
        "SUPER SHIFT, B, exec, toggle_waybar"
        "SUPER, C ,exec, hyprpicker -a"
        "SUPER, W,exec, wallpaper-picker"
        "SUPER, N, exec, swaync-client -t -sw"
        "SUPER SHIFT, W, exec, vm-start"

        # screenshot
        "SUPER, Print, exec, grimblast --notify --cursor copysave output ~/pic/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
        ", Print, exec, grimblast --notify --cursor --freeze copysave area ~/pic/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"

        # switch focus
        "SUPER, H, movefocus, l"
        "SUPER, J, movefocus, d"
        "SUPER, K, movefocus, u"
        "SUPER, L, movefocus, r"

        # switch workspace
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

        # same as above, but switch to the workspace
        "SUPER SHIFT, 1, movetoworkspacesilent, 1" # movetoworkspacesilent
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

        # window control
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

        # media and volume controls
        ",XF86AudioMute, exec, pamixer -t"
        ",XF86AudioPlay, exec, playerctl play-pause"
        ",XF86AudioNext, exec, playerctl next"
        ",XF86AudioPrev, exec, playerctl previous"
        ",XF86AudioStop, exec, playerctl stop"

        "SUPER, mouse_down, workspace, e-1"
        "SUPER, mouse_up, workspace, e+1"

        # clipboard manager
        "SUPER, V, exec, cliphist list | rofi -dmenu -theme-str 'window {width: 50%;}' | cliphist decode | wl-copy"
      ];

      # binds active in lockscreen
      bindl = [
        # laptop brigthness
        ",XF86MonBrightnessUp, exec, brightnessctl set 5%+"
        ",XF86MonBrightnessDown, exec, brightnessctl set 5%-"
        "SUPER, XF86MonBrightnessUp, exec, brightnessctl set 100%+"
        "SUPER, XF86MonBrightnessDown, exec, brightnessctl set 100%-"
      ];

      # binds that repeat when held
      binde = [
        ",XF86AudioRaiseVolume,exec, pamixer -i 2"
        ",XF86AudioLowerVolume,exec, pamixer -d 2"
      ];

      # mouse binding
      bindm = [
        "SUPER, mouse:272, movewindow"
        "SUPER, mouse:273, resizewindow"
      ];

      # windowrule
      windowrule = [
        "float,qView"
        "center,qView"
        "size 1200 725,qView"
        "float,imv"
        "center,imv"
        "size 1200 725,imv"
        # "float,mpv"
        # "center,mpv"
        "tile,Aseprite"
        # "size 1200 725,mpv"
        "float,title:^(float_kitty)$"
        "center,title:^(float_kitty)$"
        "size 950 600,title:^(float_kitty)$"
        "float,audacious"
        "pin,rofi"
        "tile, neovide"
        "idleinhibit focus,mpv"
        "float,udiskie"
        "float,title:^(Transmission)$"
        "float,title:^(Volume Control)$"
        "float,title:^(Firefox — Sharing Indicator)$"
        "move 0 0,title:^(Firefox — Sharing Indicator)$"
        "size 700 450,title:^(Volume Control)$"
        "move 40 55%,title:^(Volume Control)$"
      ];

      # windowrulev2
      windowrulev2 = [
        "float, title:^(Picture-in-Picture)$"
        "opacity 1.0 override 1.0 override, title:^(Picture-in-Picture)$"
        "pin, title:^(Picture-in-Picture)$"
        "opacity 1.0 override 1.0 override, title:^(.*imv.*)$"
        "opacity 1.0 override 1.0 override, title:^(.*mpv.*)$"
        "opacity 1.0 override 1.0 override, class:(Aseprite)"
        "opacity 1.0 override 1.0 override, class:(Unity)"
        "opacity 1.0 override 1.0 override, class:(floorp)"
        "opacity 1.0 override 1.0 override, class:(evince)"
        "workspace 1, class:^(floorp)$"
        "workspace 4, class:^(discord)$"
        "workspace 4, class:^(Gimp-2.10)$"
        "workspace 4, class:^(Aseprite)$"
        "workspace 5, class:^(Audacious)$"
        "workspace 5, class:^(Spotify)$"
        "idleinhibit focus, class:^(mpv)$"
        "idleinhibit fullscreen, class:^(firefox)$"
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
      ];

    };

    extraConfig = "
      monitor=DP-4,3840x2160@119.999001,0x0,1
    ";
  };
}
