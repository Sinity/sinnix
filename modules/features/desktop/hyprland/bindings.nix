# Hyprland keybindings configuration
{
  pkgs,
  scriptPkgs,
  sinnix,
  ...
}:
let
  script = rel: "${sinnix.paths.projectRoot}/scripts/${rel}";
  screenshotDir = "${sinnix.paths.capturesRoot}/screenshot";
in
{
  bind = [
    "SUPER, Return, exec, kitty --single-instance --instance-group terminal"
    "SUPER, Q, killactive"
    "SUPER, F, fullscreen, 0"
    # Launcher + lock are Noctalia surfaces (IPC).
    "SUPER, D, exec, noctalia msg panel-toggle launcher"
    "SUPER, Escape, exec, qs -c noctalia-shell ipc call lockScreen toggle"
    "SUPER, Slash, exec, qs -c noctalia-shell ipc call plugin:keybind-cheatsheet toggle"

    "SUPER, H, exec, ${script "kitty-hypr-nav"} focus left"
    "SUPER, J, exec, ${script "kitty-hypr-nav"} focus down"
    "SUPER, K, exec, ${script "kitty-hypr-nav"} focus up"
    "SUPER, L, exec, ${script "kitty-hypr-nav"} focus right"

    "SUPER SHIFT, H, exec, ${script "kitty-hypr-nav"} move left"
    "SUPER SHIFT, L, exec, ${script "kitty-hypr-nav"} move right"
    "SUPER SHIFT, K, exec, ${script "kitty-hypr-nav"} move up"
    "SUPER SHIFT, J, exec, ${script "kitty-hypr-nav"} move down"

    "SUPER, Space, exec, hyprctl dispatch togglefloating && hyprctl dispatch centerwindow"

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

    "SUPER SHIFT, 1, movetoworkspace, 1"
    "SUPER SHIFT, 2, movetoworkspace, 2"
    "SUPER SHIFT, 3, movetoworkspace, 3"
    "SUPER SHIFT, 4, movetoworkspace, 4"
    "SUPER SHIFT, 5, movetoworkspace, 5"
    "SUPER SHIFT, 6, movetoworkspace, 6"
    "SUPER SHIFT, 7, movetoworkspace, 7"
    "SUPER SHIFT, 8, movetoworkspace, 8"
    "SUPER SHIFT, 9, movetoworkspace, 9"
    "SUPER SHIFT, 0, movetoworkspace, 10"

    # Disabled for now (user request): term (SUPER+grave) + notes (SUPER+N) scratchpads.
    # "SUPER, grave, exec, uwsm app -- ${script "toggle-scratch"} term"
    "SUPER, S, exec, uwsm app -- ${script "toggle-scratch"} spotify"
    # "SUPER, N, exec, uwsm app -- ${script "toggle-scratch"} notes"

    "SUPER, V, exec, uwsm app -- kitty --class clipse -e clipse"
    ", Print, exec, ${script "hdr-screenshot"} area --dir ${screenshotDir}"
    "SUPER, Print, exec, ${script "hdr-screenshot"} output --dir ${screenshotDir}"

    # F-key bindings
    ", F3, exec, asbl-no-moar once --mode invert --duration 0.05"
    ", F6, exec, uwsm app -- ${script "toggle-scratch"} weechat"
    ", F8, exec, uwsm app -- ${script "toggle-scratch"} rawlog"
    ", F9, exec, sudo -n ${scriptPkgs.nuke-builds}/bin/nuke-builds"

    # Gaming: replay buffer (F10 = toggle/save, Shift+F10 = stop)
    ", F10, exec, replay-buffer"
    "SHIFT, F10, exec, replay-buffer-stop"
    # Gaming: MangoHud toggle is Shift_R+F12 (handled by MangoHud itself)

    # Numpad browser scratchpads (numlock OFF)
    ", KP_Left, exec, uwsm app -- ${script "browser-scratchpad"} chatgpt https://chatgpt.com"
    ", KP_Begin, exec, uwsm app -- ${script "browser-scratchpad"} claude https://claude.ai"
    ", KP_Right, exec, uwsm app -- ${script "browser-scratchpad"} aistudio https://aistudio.google.com"
    ", KP_Home, exec, uwsm app -- ${script "browser-scratchpad"} raindrop https://app.raindrop.io"
    ", KP_Up, exec, uwsm app -- ${script "browser-scratchpad"} ytmusic https://music.youtube.com"
    ", KP_Prior, exec, uwsm app -- ${script "browser-scratchpad"} youtube https://youtube.com"

    "SUPER SHIFT, P, pin"

    "SUPER, C, exec, uwsm app -- ${script "open-code-editor"}"
    "SUPER, B, exec, uwsm app -- qutebrowser --target window"
    "SUPER SHIFT, B, exec, uwsm app -- qutebrowser --target window"
    "SUPER, G, togglegroup"
    "SUPER SHIFT, G, exec, uwsm app -- ${script "kitty-grid"}"
    "SUPER CTRL, G, exec, uwsm app -- ${script "kitty-grid"} --grid 3x3"
    "SUPER SHIFT, C, exec, uwsm app -- ${script "kitty-grid"} --class qutebrowser --grid 3x2 --arrange-only"

    ",XF86AudioMute, exec, pamixer -t"
    ",XF86AudioPlay, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
    ",XF86AudioNext, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioPrev, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioRaiseVolume, exec, pamixer -i 2"
    ",XF86AudioLowerVolume, exec, pamixer -d 2"
    "SUPER, XF86AudioMute, exec, ${script "audio"} mic-toggle"
    "SUPER, XF86AudioRaiseVolume, exec, ${script "audio"} toggle"

    "SUPER, Tab, changegroupactive, f"
    "SUPER SHIFT, Tab, changegroupactive, b"
    "SUPER, T, togglegroup"
    "SUPER SHIFT, T, lockactivegroup, toggle"

    "SUPER CTRL, H, exec, ${script "kitty-hypr-nav"} resize left"
    "SUPER CTRL, L, exec, ${script "kitty-hypr-nav"} resize right"
    "SUPER CTRL, K, exec, ${script "kitty-hypr-nav"} resize up"
    "SUPER CTRL, J, exec, ${script "kitty-hypr-nav"} resize down"

    "SUPER ALT, H, moveactive, -80 0"
    "SUPER ALT, L, moveactive, 80 0"
    "SUPER ALT, K, moveactive, 0 -80"
    "SUPER ALT, J, moveactive, 0 80"

    "SUPER, P, pseudo"
    "SUPER, Y, layoutmsg, togglesplit"
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
}
