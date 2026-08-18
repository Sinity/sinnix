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
  bindd = [
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
    # Maximalist companion to the plugin above: not just Hyprland binds, but
    # the sinnix CLI, shared skills, and curated beads/git/agent-dispatch
    # references, all regenerated fresh on open
    # (sinnix-v034). Regenerate-then-open, not a static file.
    "SUPER SHIFT, Slash, Open the full sinnix cheatsheet, exec, ${script "sinnix-cheatsheet"} && ${script "sinnix-browser-app"} http://127.0.0.1:8880/reports/cheatsheet.html"
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
    # "SUPER, N, exec, uwsm app -- ${script "toggle-scratch"} notes"

    "SUPER, V, Browse clipboard history, exec, uwsm app -- kitty --class clipse -e clipse"
    ", Print, Screenshot a region, exec, noctalia msg screenshot-region"
    "SUPER, Print, Screenshot the whole screen, exec, noctalia msg screenshot-fullscreen"

    # F-key bindings
    ", F3, Pulse the OLED panel to clear burn-in dimming, exec, asbl-no-moar once --mode invert --duration 0.05"

    # Screen-shader playground. SHIFT+F4 is the way out of a shader that makes
    # the screen unreadable, so it must stay bound to something that restores
    # fp16 and damage tracking, not a bare screen_shader clear.
    ", F4, Apply the next screen shader, exec, ${scriptPkgs.sinnix-shader}/bin/sinnix-shader next"
    "SHIFT, F4, Clear the screen shader, exec, ${scriptPkgs.sinnix-shader}/bin/sinnix-shader off"
    "SUPER, F4, Apply a random screen shader, exec, ${scriptPkgs.sinnix-shader}/bin/sinnix-shader random"
    "SUPER SHIFT, F4, Start screen-shader playback, exec, ${scriptPkgs.sinnix-shader}/bin/sinnix-shader play --random --interval 6 --crossfade 1.5"
    ", F6, Toggle the WeeChat scratchpad, exec, uwsm app -- ${script "toggle-scratch"} weechat"
    # The agent browser lives on a hidden special workspace and is otherwise
    # invisible; this is the only way to look at what an agent is doing in it.
    # A plain toggle rather than a scratchpad script because the window is
    # already parked there by a windowrule -- nothing needs launching, only
    # showing. Sits between the other two F-key scratchpads on purpose: it is
    # the same gesture for the same kind of thing.
    ", F7, Toggle the agent browser into view, togglespecialworkspace, agentbrowser"
    ", F8, Toggle the raw-log scratchpad, exec, uwsm app -- ${script "toggle-scratch"} rawlog"
    ", F9, Emergency stop for runaway builds and background work, exec, sudo -n ${scriptPkgs.nuke-builds}/bin/nuke-builds"

    # Replay ring (F10 = save, Shift+F10 = stop) -- always-on capture
    # surface (capture-replay.nix), not gaming-specific.
    ", F10, Save the screen replay ring, exec, sinnix-replay-save"
    "SHIFT, F10, Stop the screen replay ring, exec, sinnix-replay-stop"
    # Gaming: MangoHud toggle is Shift_R+F12 (handled by MangoHud itself)

    "SUPER, C, Open the code editor, exec, uwsm app -- ${script "open-code-editor"}"
    "SUPER, B, Open a new Chrome window, exec, uwsm app -- sinnix-chrome --new-window"
    "SUPER, G, Group or ungroup the window, togglegroup"
    "SUPER SHIFT, G, Open a grid of terminals, exec, uwsm app -- ${script "kitty-grid"}"
    "SUPER CTRL, G, Open a 3x3 grid of terminals, exec, uwsm app -- ${script "kitty-grid"} --grid 3x3"

    ",XF86AudioMute, Mute or unmute audio, exec, pamixer -t"
    ",XF86AudioPlay, Play or pause media, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
    ",XF86AudioNext, Skip to the next track, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioPrev, Go back to the previous track, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioRaiseVolume, Raise the volume, exec, pamixer -i 2"
    ",XF86AudioLowerVolume, Lower the volume, exec, pamixer -d 2"
    "SUPER, XF86AudioMute, Mute or unmute the microphone, exec, ${script "audio"} mic-toggle"
    "SUPER, XF86AudioRaiseVolume, Switch to the next audio output, exec, ${script "audio"} toggle"

    # The #1 measured behavior on this desktop (workspace 1<->2 toggling,
    # thousands of fires) had no dedicated key; group-cycling here was
    # near-zero usage, so Tab is freed for it.
    "SUPER, Tab, Switch to the previous workspace, workspace, previous"
    "SUPER SHIFT, Tab, Cycle backward through the group, changegroupactive, b"

    "SUPER CTRL, H, Shrink or grow the window leftward, exec, ${script "kitty-hypr-nav"} resize left"
    "SUPER CTRL, L, Shrink or grow the window rightward, exec, ${script "kitty-hypr-nav"} resize right"
    "SUPER CTRL, K, Shrink or grow the window upward, exec, ${script "kitty-hypr-nav"} resize up"
    "SUPER CTRL, J, Shrink or grow the window downward, exec, ${script "kitty-hypr-nav"} resize down"
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
  ];
}
