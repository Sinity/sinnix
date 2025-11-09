# Hyprland keybindings configuration
{ inputs, pkgs, sinnix, ... }:
let
  script = rel: "${inputs.self}/scripts/${rel}";
  screenshotDir = "${sinnix.paths.dataRoot}/screenshot";
in
{
  bind = [
    "SUPER, Return, exec, kitty"
    "SUPER, Q, killactive"
    "SUPER, F, fullscreen, 0"
    "SUPER, D, exec, tofi-drun --drun-launch=true"
    "SUPER, Escape, exec, hyprlock"

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

    "SUPER, grave, exec, pypr toggle term"
    "SUPER, S, exec, pypr toggle spotify"
    "SUPER, N, exec, pypr toggle notes"

    "SUPER, V, exec, kitty --class clipse -e clipse"
    ", Print, exec, grimblast --notify --freeze copysave area ${screenshotDir}/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
    "SUPER, Print, exec, grimblast --notify --cursor copysave output ${screenshotDir}/$(date +'%Y-%m-%d-At-%Ih%Mm%Ss').png"
    ", F8, exec, pypr toggle rawlog"
    ", SHIFT+F8, exec, log-to-knowledgebase"

    "SUPER SHIFT, P, pin"

    "SUPER, C, exec, ${pkgs.bash}/bin/bash -lc 'command -v code >/dev/null && code --reuse-window || codium --reuse-window'"
    "SUPER, B, exec, qutebrowser --target window"
    "SUPER SHIFT, B, exec, qutebrowser --target window"
    "SUPER, G, togglegroup"
    "SUPER SHIFT, G, exec, ${script "kitty-grid"}"
    "SUPER CTRL, G, exec, ${script "kitty-grid"} --grid 3x3"
    "SUPER SHIFT, C, exec, ${script "kitty-grid"} --class qutebrowser --grid 3x2 --arrange-only"
    "SUPER SHIFT, N, exec, ~/.local/bin/kb-capture"
    "SUPER, W, exec, kitty --class session-menu --title SessionMenu -e idea-session menu"
    "SUPER SHIFT, W, exec, kitty --class session-menu --title SessionNew -e idea-session new"

    ",XF86AudioMute, exec, pamixer -t"
    ",XF86AudioPlay, exec, playerctl play-pause && notify-send -t 1000 '♪ Media' '$(playerctl status)'"
    ",XF86AudioNext, exec, playerctl next && notify-send -t 1000 '♪ Next' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioPrev, exec, playerctl previous && notify-send -t 1000 '♪ Previous' '$(playerctl metadata title 2>/dev/null || echo \"Unknown\")'"
    ",XF86AudioRaiseVolume, exec, pamixer -i 2"
    ",XF86AudioLowerVolume, exec, pamixer -d 2"

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
}
