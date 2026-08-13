# Hyprland keybindings configuration.
#
# Every user-facing bind uses the described family (bindd / binddl / binddm)
# so `hyprctl binds -j` carries a human description. That description string
# is the substrate the Noctalia keybind-cheatsheet plugin (SUPER+/) renders,
# so write descriptions for the cheatsheet reader: verb first, no commas
# (hyprlang splits the bind line on them), no implementation jargon.
{
  pkgs,
  scriptPkgs,
  sinnix,
  ...
}:
let
  script = rel: "${sinnix.paths.projectRoot}/scripts/${rel}";
in
{
  submaps.system.settings = {
    bindd = [
      ", S, Screenshot region, exec, noctalia msg screenshot-region"
      ", F, Screenshot fullscreen, exec, noctalia msg screenshot-fullscreen"
      ", R, Save replay ring, exec, sinnix-replay-save"
      "SHIFT, R, Stop replay ring, exec, sinnix-replay-stop"
      ", P, Park background work, exec, sinnix-pressure-park auto"
      ", T, Thaw parked background work, exec, sinnix-pressure-park thaw"
      ", M, Pulse OLED ASBL, exec, asbl-no-moar once --mode invert --duration 0.05"
      ", H, Show display capture status, exec, sinnix-screenshot-control probe"
      ", Escape, Exit system controls, submap, reset"
      ", Return, Exit system controls, submap, reset"
    ];
  };

  bindd = [
    "SUPER, End, Open Sinnix system controls, submap, system"
    "SUPER SHIFT, Return, Launch Codex in focused Kitty directory, exec, sinnix-kitty-control launch-agent-here --agent codex"
    "SUPER SHIFT, O, OCR selected region to clipboard, exec, hyprland-ocr"
    "SUPER SHIFT, Z, Increase cursor magnification, exec, hyprctl keyword cursor:zoom_factor 2.0"
    "SUPER SHIFT, X, Reset cursor magnification, exec, hyprctl keyword cursor:zoom_factor 1.0"
    "SUPER SHIFT, Escape, Dismiss visible scratchpads, exec, dismiss-scratchpads"
    "SUPER SHIFT, F, Smart fullscreen, fullscreen, 1"

    "SUPER, Return, Open a terminal, exec, kitty --single-instance --instance-group terminal"
    "SUPER, Q, Close the focused window, killactive"
    "SUPER, F, Toggle fullscreen, fullscreen, 0"
    # Launcher + lock are Noctalia surfaces (IPC).
    "SUPER, D, Open the app launcher, exec, noctalia msg panel-toggle launcher"
    "SUPER, Escape, Lock the session, exec, noctalia msg session lock"
    "SUPER, Slash, Show this keybind cheatsheet, exec, noctalia msg panel-toggle kenn/keybind-cheatsheet:cheatsheet"
    "SUPER, A, Jump to the oldest agent needing attention, exec, ${script "sinnix-attention"}"
    # Unified picker (sinnix-r4u8 browser-inversion front door): history +
    # bookmarks + clipboard + recent project dirs, one fuzzy surface.
    # scriptPkgs (not the raw `script` helper) so runtimeInputs land on
    # PATH -- this script shells out to fuzzel/kitty/zoxide/wl-copy.
    "SUPER, O, Search history bookmarks clipboard and projects, exec, ${scriptPkgs.sinnix-picker}/bin/sinnix-picker"

    "SUPER, H, Focus the window to the left, exec, ${script "kitty-hypr-nav"} focus left"
    "SUPER, J, Focus the window below, exec, ${script "kitty-hypr-nav"} focus down"
    "SUPER, K, Focus the window above, exec, ${script "kitty-hypr-nav"} focus up"
    "SUPER, L, Focus the window to the right, exec, ${script "kitty-hypr-nav"} focus right"

    "SUPER SHIFT, H, Move the window left, exec, ${script "kitty-hypr-nav"} move left"
    "SUPER SHIFT, L, Move the window right, exec, ${script "kitty-hypr-nav"} move right"
    "SUPER SHIFT, K, Move the window up, exec, ${script "kitty-hypr-nav"} move up"
    "SUPER SHIFT, J, Move the window down, exec, ${script "kitty-hypr-nav"} move down"

    "SUPER, Space, Float and center the window, exec, hyprctl dispatch togglefloating && hyprctl dispatch centerwindow"

    "SUPER, 1, Switch to workspace 1, workspace, 1"
    "SUPER, 2, Switch to workspace 2, workspace, 2"
    "SUPER, 3, Switch to workspace 3, workspace, 3"
    "SUPER, 4, Switch to workspace 4, workspace, 4"
    "SUPER, 5, Switch to workspace 5, workspace, 5"
    "SUPER, 6, Switch to workspace 6, workspace, 6"
    "SUPER, 7, Switch to workspace 7, workspace, 7"
    "SUPER, 8, Switch to workspace 8, workspace, 8"
    "SUPER, 9, Switch to workspace 9, workspace, 9"
    "SUPER, 0, Switch to workspace 10, workspace, 10"

    "SUPER SHIFT, 1, Move the window to workspace 1, movetoworkspace, 1"
    "SUPER SHIFT, 2, Move the window to workspace 2, movetoworkspace, 2"
    "SUPER SHIFT, 3, Move the window to workspace 3, movetoworkspace, 3"
    "SUPER SHIFT, 4, Move the window to workspace 4, movetoworkspace, 4"
    "SUPER SHIFT, 5, Move the window to workspace 5, movetoworkspace, 5"
    "SUPER SHIFT, 6, Move the window to workspace 6, movetoworkspace, 6"
    "SUPER SHIFT, 7, Move the window to workspace 7, movetoworkspace, 7"
    "SUPER SHIFT, 8, Move the window to workspace 8, movetoworkspace, 8"
    "SUPER SHIFT, 9, Move the window to workspace 9, movetoworkspace, 9"
    "SUPER SHIFT, 0, Move the window to workspace 10, movetoworkspace, 10"

    # Disabled for now (user request): term (SUPER+grave) + notes (SUPER+N) scratchpads.
    # "SUPER, grave, exec, uwsm app -- ${script "toggle-scratch"} term"
    "SUPER, S, Toggle the Spotify scratchpad, exec, uwsm app -- ${script "toggle-scratch"} spotify"
    # "SUPER, N, exec, uwsm app -- ${script "toggle-scratch"} notes"

    "SUPER, V, Browse clipboard history, exec, uwsm app -- kitty --class clipse -e clipse"
    ", Print, Screenshot a region, exec, noctalia msg screenshot-region"
    "SUPER, Print, Screenshot the whole screen, exec, noctalia msg screenshot-fullscreen"

    # F-key bindings
    ", F3, Pulse the OLED panel to clear burn-in dimming, exec, asbl-no-moar once --mode invert --duration 0.05"
    ", F6, Toggle the WeeChat scratchpad, exec, uwsm app -- ${script "toggle-scratch"} weechat"
    ", F8, Toggle the raw-log scratchpad, exec, uwsm app -- ${script "toggle-scratch"} rawlog"
    ", F9, Emergency stop for runaway builds and background work, exec, sudo -n ${scriptPkgs.nuke-builds}/bin/nuke-builds"

    # Replay ring (F10 = save, Shift+F10 = stop) -- always-on capture
    # surface (capture-replay.nix), not gaming-specific.
    ", F10, Save the screen replay ring, exec, sinnix-replay-save"
    "SHIFT, F10, Stop the screen replay ring, exec, sinnix-replay-stop"
    # Gaming: MangoHud toggle is Shift_R+F12 (handled by MangoHud itself)

    # Numpad browser scratchpads (numlock OFF)
    ", KP_Left, Toggle the ChatGPT scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} chatgpt https://chatgpt.com"
    ", KP_Begin, Toggle the Claude scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} claude https://claude.ai"
    ", KP_Right, Toggle the AI Studio scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} aistudio https://aistudio.google.com"
    ", KP_Home, Toggle the Raindrop bookmarks scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} raindrop https://app.raindrop.io"
    ", KP_Up, Toggle the YouTube Music scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} ytmusic https://music.youtube.com"
    ", KP_Prior, Toggle the YouTube scratchpad, exec, uwsm app -- ${script "browser-scratchpad"} youtube https://youtube.com"

    "SUPER SHIFT, P, Pin the window above all workspaces, pin"

    "SUPER, C, Open the code editor, exec, uwsm app -- ${script "open-code-editor"}"
    "SUPER, B, Open a browser window, exec, uwsm app -- qutebrowser --target window"
    "SUPER SHIFT, B, Open a browser window, exec, uwsm app -- qutebrowser --target window"
    "SUPER, G, Group or ungroup the window, togglegroup"
    "SUPER, bracketleft, Add the window to the group on the left, moveintogroup, l"
    "SUPER, bracketright, Add the window to the group on the right, moveintogroup, r"
    "SUPER SHIFT, bracketleft, Take the window out of its group, moveoutofgroup"
    "SUPER SHIFT, G, Open a grid of terminals, exec, uwsm app -- ${script "kitty-grid"}"
    "SUPER CTRL, G, Open a 3x3 grid of terminals, exec, uwsm app -- ${script "kitty-grid"} --grid 3x3"
    "SUPER SHIFT, C, Arrange browser windows into a grid, exec, uwsm app -- ${script "kitty-grid"} --class qutebrowser --grid 3x2 --arrange-only"

    ",XF86AudioMute, Mute or unmute audio, exec, pamixer -t"
    ",XF86AudioPlay, Play or pause media, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
    ",XF86AudioNext, Skip to the next track, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioPrev, Go back to the previous track, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioRaiseVolume, Raise the volume, exec, pamixer -i 2"
    ",XF86AudioLowerVolume, Lower the volume, exec, pamixer -d 2"
    "SUPER, XF86AudioMute, Mute or unmute the microphone, exec, ${script "audio"} mic-toggle"
    "SUPER, XF86AudioRaiseVolume, Switch to the next audio output, exec, ${script "audio"} toggle"

    "SUPER, Tab, Cycle forward through the group, changegroupactive, f"
    "SUPER SHIFT, Tab, Cycle backward through the group, changegroupactive, b"
    "SUPER SHIFT, T, Lock the group so new windows stay out, lockactivegroup, toggle"

    "SUPER CTRL, H, Shrink or grow the window leftward, exec, ${script "kitty-hypr-nav"} resize left"
    "SUPER CTRL, L, Shrink or grow the window rightward, exec, ${script "kitty-hypr-nav"} resize right"
    "SUPER CTRL, K, Shrink or grow the window upward, exec, ${script "kitty-hypr-nav"} resize up"
    "SUPER CTRL, J, Shrink or grow the window downward, exec, ${script "kitty-hypr-nav"} resize down"

    "SUPER ALT, H, Nudge the floating window left, moveactive, -80 0"
    "SUPER ALT, L, Nudge the floating window right, moveactive, 80 0"
    "SUPER ALT, K, Nudge the floating window up, moveactive, 0 -80"
    "SUPER ALT, J, Nudge the floating window down, moveactive, 0 80"

    "SUPER, P, Toggle pseudo-tiling for the window, pseudo"
    "SUPER, Y, Flip the tiling split direction, layoutmsg, togglesplit"
  ];

  # binddl / binddm: the described variants of bindl (works while locked) and
  # bindm (mouse drag). Flag letters combine in any order; verified against
  # Hyprland 0.55.4 via `hyprctl keyword binddl ...` returning has_description.
  binddl = [
    ",XF86MonBrightnessUp, Raise screen brightness, exec, brightnessctl set 5%+"
    ",XF86MonBrightnessDown, Lower screen brightness, exec, brightnessctl set 5%-"
    "SUPER, XF86MonBrightnessUp, Set screen brightness to maximum, exec, brightnessctl set 100%+"
    "SUPER, XF86MonBrightnessDown, Set screen brightness to minimum, exec, brightnessctl set 100%-"
  ];

  binddm = [
    "SUPER, mouse:272, Drag to move the window, movewindow"
    "SUPER, mouse:273, Drag to resize the window, resizewindow"
    "SUPER ALT, mouse:272, Drag to resize the window, resizewindow"
  ];
}
