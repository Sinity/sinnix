# Hyprland window rules configuration
{ lib, hyprlandPkg }:
let
  useNewIdleRule = lib.versionAtLeast hyprlandPkg.version "0.52.0";
  idleRuleName = if useNewIdleRule then "idleinhibit" else "idle_inhibit";
  stripMatch =
    cond:
    let
      rest = lib.removePrefix "match:" cond;
      groups = builtins.match "^[[:space:]]*([^[:space:]]+)[[:space:]]+(.*)$" rest;
    in
    if !lib.hasPrefix "match:" cond then
      cond
    else if groups == null then
      rest
    else
      "${builtins.elemAt groups 0}:${builtins.elemAt groups 1}";
  idleRules = [
    { mode = "focus"; condition = "match:class ^(mpv)$"; }
    { mode = "fullscreen"; condition = "match:class ^(firefox)$"; }
    { mode = "fullscreen"; condition = "match:class ^(qutebrowser)$"; }
    { mode = "focus"; condition = "match:title .*[Yy]ou[Tt]ube.*"; }
    { mode = "focus"; condition = "match:title .*- YouTube$"; }
    { mode = "focus"; condition = "match:title .*YouTube.*"; }
    { mode = "focus"; condition = "match:title .*Netflix.*"; }
    { mode = "focus"; condition = "match:title .*Twitch.*"; }
    { mode = "focus"; condition = "match:title .*Prime Video.*"; }
  ];
in
{
  windowrule =
    (if useNewIdleRule then [ ] else map (rule: "${idleRuleName} ${rule.mode}, ${rule.condition}") idleRules)
    ++ [

    "float, title:^(Open File)$"
    "float, title:^(Save As)$"
    "float, class:^(nm-connection-editor)$"
    "float, pin, size 480 270, move monitor_w-500 50, title:^(Picture-in-Picture)$"

    "workspace special:music, class:^(music)$"
    "workspace special:music, title:^(ncspot)$"
    "workspace special:music, class:^(pwvucontrol)$"
    "workspace special:music, class:^(blueman-manager)$"
    "float, size monitor_w*0.40 monitor_h*0.45, move monitor_w*0.02 monitor_h*0.55, opacity 0.8 0.8, class:^(blueman-manager)$"
    "opacity 0.8 0.8, class:^(pwvucontrol)$"

    "workspace special:scratch_term silent, class:^(scratchpad-terminal)$"
    "float, class:^(scratchpad-terminal)$"
    "center, class:^(scratchpad-terminal)$"
    "size monitor_w*0.75 monitor_h*0.55, class:^(scratchpad-terminal)$"

    "workspace special:scratch_notes silent, class:^(notes-scratch)$"
    "float, class:^(notes-scratch)$"
    "center, class:^(notes-scratch)$"
    "size monitor_w*0.70 monitor_h*0.50, class:^(notes-scratch)$"

    "workspace special:scratch_rawlog silent, class:^(rawlog-capture)$"
    "float, class:^(rawlog-capture)$"
    "center, class:^(rawlog-capture)$"
    "size monitor_w*0.72 monitor_h*0.48, class:^(rawlog-capture)$"

    "workspace special:scratch_spotify silent, class:^([Ss]potify)$"
    "float, class:^([Ss]potify)$"
    "center, class:^([Ss]potify)$"
    "size monitor_w*0.85 monitor_h*0.85, class:^([Ss]potify)$"

    "float, center, size 2000 1000, class:(clipse)"

    "immediate, fullscreen, workspace 5, class:^(steam_app_.*)$"

    "float, size 1200 800, center, class:^(xdg-desktop-portal-gtk)$"

    "tile, class:^(qutebrowser)$"
    "group set, class:^(qutebrowser)$"
    "float, size monitor_w*0.28 monitor_h*0.24, move monitor_w*0.70 monitor_h*0.06, class:^(qutebrowser)$, floating:1"
    "float, center, class:^(imv)$"
  ];

  windowrulev2 =
    lib.optionals useNewIdleRule (map (rule: "${idleRuleName} ${rule.mode}, ${stripMatch rule.condition}") idleRules);
}
