# Hyprland Lua keybindings.
#
# The values below are semantic `hl.bind` calls. Home Manager's Lua renderer
# expands `_args` into call arguments and `mkLuaInline` keeps dispatchers as Lua
# expressions rather than serializing legacy hyprlang strings.
{
  lib,
  scriptPkgs,
  sinnix,
  ...
}:
let
  inherit (lib.generators) mkLuaInline toLua;
  script = rel: "${sinnix.paths.projectRoot}/scripts/${rel}";
  lua = mkLuaInline;
  string = value: toLua { } value;
  call = name: args: lua "hl.dsp.${name}(${args})";
  callback = body: lua "function() ${body} end";
  exec = command: call "exec_cmd" (string command);
  bind = keys: description: dispatcher: extra: {
    _args = [
      keys
      dispatcher
      ({ inherit description; } // extra)
    ];
  };
  simple =
    keys: description: dispatcher:
    bind keys description dispatcher { };
  run =
    keys: description: command:
    simple keys description (exec command);
  workspace = id: call "focus" "{ workspace = ${toString id} }";
  moveWorkspace = id: call "window.move" "{ workspace = ${toString id} }";
  locked =
    keys: description: command:
    bind keys description (exec command) {
      locked = true;
      repeating = true;
    };
  mouse =
    keys: description: dispatcher:
    bind keys description dispatcher { mouse = true; };

  bindd = [
    (run "SUPER + SHIFT + Return" "Launch Codex in focused Kitty directory"
      "sinnix-kitty-control launch-agent-here --agent codex"
    )
    (run "SUPER + SHIFT + O" "OCR selected region to clipboard" "hyprland-ocr")
    (run "SUPER + SHIFT + Z" "Increase cursor magnification" "hyprctl keyword cursor:zoom_factor 2.0")
    (run "SUPER + SHIFT + X" "Reset cursor magnification" "hyprctl keyword cursor:zoom_factor 1.0")
    (run "SUPER + SHIFT + Escape" "Dismiss visible scratchpads" "dismiss-scratchpads")
    (simple "SUPER + SHIFT + F" "Smart fullscreen" (
      call "window.fullscreen" ''{ mode = "fullscreen", action = "toggle" }''
    ))
    (run "SUPER + Return" "Open a terminal" "kitty --single-instance --instance-group terminal")
    (simple "SUPER + Q" "Close the focused window" (call "window.close" ""))
    (simple "SUPER + F" "Toggle fullscreen" (
      call "window.fullscreen" ''{ mode = "fullscreen", action = "toggle" }''
    ))
    (run "SUPER + D" "Open the app launcher" "noctalia msg panel-toggle launcher")
    (run "SUPER + Escape" "Lock the session" "noctalia msg session lock")
    (run "SUPER + Slash" "Show this keybind cheatsheet"
      "noctalia msg panel-toggle kenn/keybind-cheatsheet:cheatsheet"
    )
    (run "SUPER + SHIFT + Slash" "Open the full sinnix cheatsheet"
      "${script "sinnix-cheatsheet"} && ${script "sinnix-browser-app"} http://127.0.0.1:8880/reports/cheatsheet.html"
    )
    (run "SUPER + H" "Focus the window to the left" "${script "kitty-hypr-nav"} focus left")
    (run "SUPER + J" "Focus the window below" "${script "kitty-hypr-nav"} focus down")
    (run "SUPER + K" "Focus the window above" "${script "kitty-hypr-nav"} focus up")
    (run "SUPER + L" "Focus the window to the right" "${script "kitty-hypr-nav"} focus right")
    (run "SUPER + SHIFT + H" "Move the window left" "${script "kitty-hypr-nav"} move left")
    (run "SUPER + SHIFT + L" "Move the window right" "${script "kitty-hypr-nav"} move right")
    (run "SUPER + SHIFT + K" "Move the window up" "${script "kitty-hypr-nav"} move up")
    (run "SUPER + SHIFT + J" "Move the window down" "${script "kitty-hypr-nav"} move down")
    (simple "SUPER + Space" "Float and center the window" (
      callback ''hl.dispatch(hl.dsp.window.float({ action = "toggle" })); hl.dispatch(hl.dsp.window.center())''
    ))
    (simple "SUPER + 1" "Switch to workspace 1" (workspace 1))
    (simple "SUPER + 2" "Switch to workspace 2" (workspace 2))
    (simple "SUPER + 3" "Switch to workspace 3" (workspace 3))
    (simple "SUPER + 4" "Switch to workspace 4" (workspace 4))
    (simple "SUPER + 5" "Switch to workspace 5" (workspace 5))
    (simple "SUPER + 6" "Switch to workspace 6" (workspace 6))
    (simple "SUPER + 7" "Switch to workspace 7" (workspace 7))
    (simple "SUPER + 8" "Switch to workspace 8" (workspace 8))
    (simple "SUPER + 9" "Switch to workspace 9" (workspace 9))
    (simple "SUPER + 0" "Switch to workspace 10" (workspace 10))
    (simple "SUPER + SHIFT + 1" "Move the window to workspace 1" (moveWorkspace 1))
    (simple "SUPER + SHIFT + 2" "Move the window to workspace 2" (moveWorkspace 2))
    (simple "SUPER + SHIFT + 3" "Move the window to workspace 3" (moveWorkspace 3))
    (simple "SUPER + SHIFT + 4" "Move the window to workspace 4" (moveWorkspace 4))
    (simple "SUPER + SHIFT + 5" "Move the window to workspace 5" (moveWorkspace 5))
    (simple "SUPER + SHIFT + 6" "Move the window to workspace 6" (moveWorkspace 6))
    (simple "SUPER + SHIFT + 7" "Move the window to workspace 7" (moveWorkspace 7))
    (simple "SUPER + SHIFT + 8" "Move the window to workspace 8" (moveWorkspace 8))
    (simple "SUPER + SHIFT + 9" "Move the window to workspace 9" (moveWorkspace 9))
    (simple "SUPER + SHIFT + 0" "Move the window to workspace 10" (moveWorkspace 10))
    (run "SUPER + V" "Browse clipboard history" "uwsm app -- kitty --class clipse -e clipse")
    (run "Print" "Screenshot a region" "noctalia msg screenshot-region")
    (run "SUPER + Print" "Screenshot the whole screen" "noctalia msg screenshot-fullscreen")
    (run "F3" "Pulse the OLED panel to clear burn-in dimming"
      "asbl-no-moar once --mode invert --duration 0.05"
    )
    (run "F4" "Apply the next screen shader" "${scriptPkgs.sinnix-shader}/bin/sinnix-shader next")
    (run "SHIFT + F4" "Clear the screen shader" "${scriptPkgs.sinnix-shader}/bin/sinnix-shader off")
    (run "SUPER + F4" "Apply a random screen shader"
      "${scriptPkgs.sinnix-shader}/bin/sinnix-shader random"
    )
    (run "SUPER + SHIFT + F4" "Start screen-shader playback"
      "${scriptPkgs.sinnix-shader}/bin/sinnix-shader play --random --interval 6 --crossfade 1.5"
    )
    (run "F6" "Toggle the WeeChat scratchpad" "uwsm app -- ${script "toggle-scratch"} weechat")
    (run "F7" "Switch to or leave the agent browser workspace" "sinnix-chrome-control toggle-agent-workspace")
    (run "F8" "Toggle the raw-log scratchpad" "uwsm app -- ${script "toggle-scratch"} rawlog")
    (run "F9" "Emergency stop for runaway builds and background work"
      "sudo -n ${scriptPkgs.nuke-builds}/bin/nuke-builds"
    )
    (run "F10" "Save the screen replay ring" "sinnix-replay-save")
    (run "SHIFT + F10" "Stop the screen replay ring" "sinnix-replay-stop")
    (run "SUPER + C" "Open the code editor" "uwsm app -- ${script "open-code-editor"}")
    (run "SUPER + B" "Open a new Chrome window" "uwsm app -- sinnix-chrome --new-window")
    (simple "SUPER + G" "Group or ungroup the window" (call "group.toggle" ""))
    (run "SUPER + SHIFT + G" "Open a grid of terminals" "uwsm app -- ${script "kitty-grid"}")
    (run "SUPER + CTRL + G" "Open a 3x3 grid of terminals"
      "uwsm app -- ${script "kitty-grid"} --grid 3x3"
    )
    (simple "SUPER + Tab" "Switch to the previous workspace" (
      call "focus" ''{ workspace = "previous" }''
    ))
    (simple "SUPER + SHIFT + Tab" "Cycle backward through the group" (call "group.prev" ""))
    (run "SUPER + CTRL + H" "Shrink or grow the window leftward"
      "${script "kitty-hypr-nav"} resize left"
    )
    (run "SUPER + CTRL + L" "Shrink or grow the window rightward"
      "${script "kitty-hypr-nav"} resize right"
    )
    (run "SUPER + CTRL + K" "Shrink or grow the window upward" "${script "kitty-hypr-nav"} resize up")
    (run "SUPER + CTRL + J" "Shrink or grow the window downward"
      "${script "kitty-hypr-nav"} resize down"
    )
    (run "XF86AudioMute" "Mute or unmute audio" "pamixer -t")
    (run "XF86AudioPlay" "Play or pause media"
      "playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
    )
    (run "XF86AudioNext" "Skip to the next track"
      "playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \\\"Unknown\\\")'"
    )
    (run "XF86AudioPrev" "Go back to the previous track"
      "playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \\\"Unknown\\\")'"
    )
    (run "XF86AudioRaiseVolume" "Raise the volume" "pamixer -i 2")
    (run "XF86AudioLowerVolume" "Lower the volume" "pamixer -d 2")
    (run "SUPER + XF86AudioMute" "Mute or unmute the microphone" "${script "audio"} mic-toggle")
    (run "SUPER + XF86AudioRaiseVolume" "Switch to the next audio output" "${script "audio"} toggle")
  ];

  binddl = [
    (locked "XF86MonBrightnessUp" "Raise screen brightness" "brightnessctl set 5%+")
    (locked "XF86MonBrightnessDown" "Lower screen brightness" "brightnessctl set 5%-")
    (locked "SUPER + XF86MonBrightnessUp" "Set screen brightness to maximum" "brightnessctl set 100%+")
    (locked "SUPER + XF86MonBrightnessDown" "Set screen brightness to minimum"
      "brightnessctl set 100%-"
    )
  ];

  binddm = [
    (mouse "SUPER + mouse:272" "Drag to move the window" (call "window.drag" ""))
    (mouse "SUPER + mouse:273" "Drag to resize the window" (call "window.resize" ""))
  ];

  submaps = { };
in
{
  inherit
    bindd
    binddl
    binddm
    submaps
    ;
}
