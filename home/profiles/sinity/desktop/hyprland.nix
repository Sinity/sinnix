{
  pkgs,
  inputs,
  lib,
  flakeRoot,
  projectLib,
  quickshellEnable ? false,
  ...
}:
let
  asset = projectLib.mkAssetPath flakeRoot;
  script = projectLib.mkScriptPath flakeRoot;
  pyprlandCleanup = pkgs.writeShellScript "pyprland-sock-cleanup" ''
    set -eu
    HYPR_RUNTIME="/run/user/$UID/hypr"
    if [ -d "$HYPR_RUNTIME" ]; then
      ${pkgs.findutils}/bin/find "$HYPR_RUNTIME" -maxdepth 2 -name ".pyprland.sock" -delete || true
    fi
  '';
in
{
  wayland.windowManager.hyprland = {
    enable = true;
    xwayland.enable = true;
    systemd.enable = false;

    settings = {
      exec-once = [
        "uwsm finalize"
      ];

      monitor = [
        ",3840x2160@120,auto,1,bitdepth,10,cm,hdr,sdrbrightness,1.4,sdrsaturation,1.0"
      ];

      xwayland.force_zero_scaling = true;

      input = {
        kb_layout = "pl";
        repeat_rate = 40;
        repeat_delay = 400;
        mouse_refocus = true;
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
        layout = "dwindle";
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
        vrr = 2;
        mouse_move_enables_dpms = true;
        key_press_enables_dpms = true;
        always_follow_on_dnd = true;
        focus_on_activate = true;
        middle_click_paste = true;
        enable_swallow = true;
        swallow_regex = "^(kitty)$";
      };

      debug = {
        disable_logs = false;
        disable_time = false;
        enable_stdout_logs = true;
      };

      decoration = {
        rounding = 0;
        active_opacity = 1.0;
        inactive_opacity = 0.7;
        dim_inactive = true;
        dim_strength = 0.3;

        blur = {
          enabled = true;
          size = 8;
          passes = 3;
          new_optimizations = true;
          vibrancy = 0.15;
          vibrancy_darkness = 0.2;
        };

        shadow = {
          enabled = true;
          range = 20;
          render_power = 3;
          offset = "0 8";
        };
      };

      animations.enabled = false;

      bind = [
        "SUPER, Return, exec, kitty"
        "SUPER, Q, killactive"
        "SUPER, F, fullscreen, 0"
        "SUPER, D, exec, tofi-drun --drun-launch=true"
        "SUPER, Escape, exec, hyprlock"

        "SUPER, H, movefocus, l"
        "SUPER, J, movefocus, d"
        "SUPER, K, movefocus, u"
        "SUPER, L, movefocus, r"

        "SUPER SHIFT, H, movewindow, l"
        "SUPER SHIFT, L, movewindow, r"
        "SUPER SHIFT, K, movewindow, u"
        "SUPER SHIFT, J, movewindow, d"

        "SUPER, Space, exec, hyprctl dispatch togglefloating && hyprctl dispatch centerwindow"

        "SUPER, 1, workspace, 1"
        "SUPER, 2, workspace, 2"
        "SUPER, 3, workspace, 3"
        "SUPER, 4, workspace, 4"
        "SUPER, 5, workspace, 5"

        "SUPER SHIFT, 1, movetoworkspace, 1"
        "SUPER SHIFT, 2, movetoworkspace, 2"
        "SUPER SHIFT, 3, movetoworkspace, 3"
        "SUPER SHIFT, 4, movetoworkspace, 4"
        "SUPER SHIFT, 5, movetoworkspace, 5"

        "SUPER, grave, exec, pypr toggle term"
        "SUPER, S, exec, pypr toggle spotify"
        "SUPER, N, exec, pypr toggle notes"

        "SUPER, V, exec, kitty --class clipse -e clipse"
        ", Print, exec, grimblast --notify --freeze copysave area /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
        "SUPER, Print, exec, grimblast --notify --cursor copysave output /realm/inbox/screenshot/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
        ", F8, exec, pypr toggle rawlog"
        ", SHIFT+F8, exec, log-to-knowledgebase"

        "SUPER SHIFT, P, pin"

        "SUPER, C, exec, ${pkgs.bash}/bin/bash -lc 'command -v code >/dev/null && code --reuse-window || codium --reuse-window'"
        "SUPER, G, exec, google-chrome-beta"
        "SUPER SHIFT, N, exec, ~/.local/bin/kb-capture"
        "SUPER, W, exec, kitty --class session-menu --title SessionMenu -e idea-session menu"
        "SUPER SHIFT, W, exec, kitty --class session-menu --title SessionNew -e idea-session new"

        ",XF86AudioMute, exec, pamixer -t"
        ",XF86AudioPlay, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
        ",XF86AudioNext, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
        ",XF86AudioPrev, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
        ",XF86AudioRaiseVolume, exec, pamixer -i 2"
        ",XF86AudioLowerVolume, exec, pamixer -d 2"

        "SUPER CTRL, H, resizeactive, -80 0"
        "SUPER CTRL, L, resizeactive, 80 0"
        "SUPER CTRL, K, resizeactive, 0 -80"
        "SUPER CTRL, J, resizeactive, 0 80"

        "SUPER ALT, H, moveactive, -80 0"
        "SUPER ALT, L, moveactive, 80 0"
        "SUPER ALT, K, moveactive, 0 -80"
        "SUPER ALT, J, moveactive, 0 80"

        "SUPER, P, pseudo"
        "SUPER, Y, togglesplit"
      ];

      bindl = [
        ",XF86MonBrightnessUp, exec, brightnessctl set 5%+"
        ",XF86MonBrightnessDown, exec, brightnessctl set 5%-"
        "SUPER, XF86MonBrightnessUp, exec, brightnessctl set 100%+"
        "SUPER, XF86MonBrightnessDown, exec, brightnessctl set 100%-"
      ];

      bindm = [
        "SUPER, mouse:272, movewindow"
        "SUPER, mouse:273, resizewindow"
        "SUPER ALT, mouse:272, resizewindow"
      ];

      windowrule = [
        "idleinhibit focus,class:^(mpv)$"
        "idleinhibit fullscreen,class:^(firefox)$"
        "idleinhibit fullscreen,class:^(google-chrome)$"
        "idleinhibit focus,title:.*[Yy]ou[Tt]ube.*"
        "idleinhibit focus,title:.*- YouTube$"
        "idleinhibit focus,title:.*YouTube.*"
        "idleinhibit focus,title:.*Netflix.*"
        "idleinhibit focus,title:.*Twitch.*"
        "idleinhibit focus,title:.*Prime Video.*"

        "float,title:^(Open File)$"
        "float,title:^(Save As)$"
        "float,class:^(pavucontrol)$"
        "float,class:^(nm-connection-editor)$"
        "center,floating:1"
        "float,title:^(Picture-in-Picture)$"
        "pin,title:^(Picture-in-Picture)$"
        "size 480 270,title:^(Picture-in-Picture)$"
        "move 100%-500 50,title:^(Picture-in-Picture)$"
        "workspace special:music,class:^(music)$"
        "workspace special:music,title:^(ncspot)$"
        "workspace special:music,class:^(pavucontrol)$"
        "workspace special:music,class:^(pwvucontrol)$"
        "workspace special:music,class:^(blueman-manager)$"
        "float,class:^(blueman-manager)$"
        "size 40% 45%,class:^(blueman-manager)$"
        "move 2% 55%,class:^(blueman-manager)$"
        "opacity 0.8 0.8,class:^(pwvucontrol)$"
        "opacity 0.8 0.8,class:^(blueman-manager)$"
        "float,class:^(scratchpad-terminal)$"
        "center,class:^(scratchpad-terminal)$"
        "float,class:^(notes-scratch)$"
        "center,class:^(notes-scratch)$"
        "size 80% 80%,class:^(notes-scratch)$"
        "float,class:(clipse)"
        "center,class:(clipse)"
        "size 2000 1000,class:(clipse)"
        "immediate,class:^(steam_app_.*)$"
        "fullscreen,class:^(steam_app_.*)$"
        "workspace 5,class:^(steam_app_.*)$"
        "float,class:^(xdg-desktop-portal-gtk)$"
        "size 1200 800,class:^(xdg-desktop-portal-gtk)$"
        "float,class:^(imv)$"
        "center,class:^(imv)$"
      ];

      windowrulev2 = [
        "size 60% 100%,title:^(session: )"
        "move 0% 0%,title:^(session: )"
        "size 40% 100%,class:^(google-chrome|google-chrome-beta|firefox|qutebrowser)$"
        "move 60% 0%,class:^(google-chrome|google-chrome-beta|firefox|qutebrowser)$"
        "float,class:^(google-chrome|google-chrome-beta)$,windowtype:=notification"
        "size 28% 24%,class:^(google-chrome|google-chrome-beta)$,windowtype:=notification"
        "move 70% 6%,class:^(google-chrome|google-chrome-beta)$,windowtype:=notification"
        "float,class:^(google-chrome|google-chrome-beta)$,windowtype:=popup"
        "size 28% 24%,class:^(google-chrome|google-chrome-beta)$,windowtype:=popup"
        "move 70% 6%,class:^(google-chrome|google-chrome-beta)$,windowtype:=popup"
      ];
    };
  };

  xdg.configFile."hypr/pyprland.toml".text = builtins.readFile (asset "pyprland.toml");

  home.file = {
    ".local/bin/kb-capture" = {
      source = script "kb-capture";
      executable = true;
    };
    ".local/bin/idea-session" = {
      source = script "idea-session";
      executable = true;
    };
    ".config/idea-session/base-agents.md" = {
      source = asset "session/base-agents.md";
    };
    ".local/bin/rawlog" = {
      source = script "rawlog";
      executable = true;
    };
    ".local/bin/rawlog-capture" = {
      source = script "rawlog-capture";
      executable = true;
    };
    ".local/bin/rawlog-capture-session" = {
      source = script "rawlog-capture-session";
      executable = true;
    };
    ".local/bin/log-to-knowledgebase" = {
      source = script "rawlog";
      executable = true;
    };
  };

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
      ExecStartPre = pyprlandCleanup;
      RuntimeDirectory = "pyprland";
      RuntimeDirectoryMode = "0755";
    };
    Install = {
      WantedBy = [ "graphical-session.target" ];
    };
  };

  xdg.configFile."hypr/hyprlock.conf".text = ''
    # BACKGROUND
    background {
      monitor =
      path = ${asset "forest.jpg"}
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
      font_size = 111
      position = 0, 270
      halign = center
      valign = center
    }

    # Day
    label {
      monitor =
      text = cmd[update:1000] echo "- $(date +"%A, %B %d") -"
      font_size = 20
      position = 0, 160
      halign = center
      valign = center
    }

    # USER-BOX
    shape {
      monitor =
      size = 350, 50
      rounding = 15
      border_size = 0
      rotate = 0

      position = 0, -230
      halign = center
      valign = center
    }

    # USER
    label {
      monitor =
      text =   $USER
      font_size = 16
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
      dots_size = 0.25
      dots_spacing = 0.4
      dots_center = true
      fade_on_empty = false
      placeholder_text = <i>Enter Password</i>
      hide_input = false
      position = 0, -300
      halign = center
      valign = center
    }
  '';

  services.hypridle = {
    enable = true;
    settings = {
      general = {
        after_sleep_cmd = "hyprctl dispatch dpms on";
        ignore_dbus_inhibit = false;
        lock_cmd = "hyprlock";
      };

      listener = [
        {
          timeout = 300;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };

  home.packages =
    (with pkgs; [
      pyprland
      brightnessctl
      hyprlock
      grim
      slurp
      grimblast
      wl-screenrec
    ])
    ++ lib.optionals quickshellEnable [
      inputs.quickshell.packages.${pkgs.system}.default
    ];
}
