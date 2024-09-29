{ inputs, pkgs, ...}: 
{
  home.packages = with pkgs; [
    swaybg
    grim slurp
    grimblast
    wl-screenrec
    hyprpicker
    wl-clip-persist
    glib
    wayland
    direnv
  ];

  systemd.user.targets.hyprland-session.Unit.Wants = [ "xdg-desktop-autostart.target" ];
  
  wayland.windowManager.hyprland = {
    enable = true;
    xwayland = {
      enable = true;
    };
    systemd.enable = true;
  };
}
