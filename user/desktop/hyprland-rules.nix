# Hyprland window rules configuration
{
  windowrule = [
    "idle_inhibit focus, match:class ^(mpv)$"
    "idle_inhibit fullscreen, match:class ^(firefox)$"
    "idle_inhibit fullscreen, match:class ^(qutebrowser)$"
    "idle_inhibit focus, match:title .*[Yy]ou[Tt]ube.*"
    "idle_inhibit focus, match:title .*- YouTube$"
    "idle_inhibit focus, match:title .*YouTube.*"
    "idle_inhibit focus, match:title .*Netflix.*"
    "idle_inhibit focus, match:title .*Twitch.*"
    "idle_inhibit focus, match:title .*Prime Video.*"

    "float 1, match:title ^(Open File)$"
    "float 1, match:title ^(Save As)$"
    "float 1, match:class ^(nm-connection-editor)$"
    "float 1, pin 1, size 480 270, move monitor_w-500 50, match:title ^(Picture-in-Picture)$"

    "workspace special:music, match:class ^(music)$"
    "workspace special:music, match:title ^(ncspot)$"
    "workspace special:music, match:class ^(pwvucontrol)$"
    "workspace special:music, match:class ^(blueman-manager)$"
    "float 1, size monitor_w*0.40 monitor_h*0.45, move monitor_w*0.02 monitor_h*0.55, opacity 0.8 0.8, match:class ^(blueman-manager)$"
    "opacity 0.8 0.8, match:class ^(pwvucontrol)$"

    "float 1, center 1, size monitor_w*0.85 monitor_h*0.85, workspace special:scratch_term silent, match:class ^(scratchpad-terminal)$"
    "float 1, center 1, size monitor_w*0.80 monitor_h*0.80, workspace special:scratch_notes silent, match:class ^(notes-scratch)$"
    "float 1, center 1, size monitor_w*0.70 monitor_h*0.40, workspace special:scratch_rawlog silent, match:class ^(rawlog-capture)$"
    "float 1, center 1, size monitor_w*0.85 monitor_h*0.85, workspace special:scratch_spotify silent, match:class ^([Ss]potify)$"

    "float 1, center 1, size 2000 1000, match:class (clipse)"

    "immediate 1, fullscreen 1, workspace 5, match:class ^(steam_app_.*)$"

    "float 1, size 1200 800, center 1, match:class ^(xdg-desktop-portal-gtk)$"

    "size monitor_w*0.60 monitor_h, match:title ^(session: )"
    "move 0 0, match:title ^(session: )"
    "tile 1, match:class ^(qutebrowser)$"
    "group set, match:class ^(qutebrowser)$"
    "float 1, size monitor_w*0.28 monitor_h*0.24, move monitor_w*0.70 monitor_h*0.06, match:class ^(qutebrowser)$, match:float true"
    "float 1, center 1, match:class ^(imv)$"
  ];
}
