# module/desktop/default.nix
{
  imports = [
    ./hyprland
    ./waybar
    ./rofi.nix
    ./swaync
    ./themes.nix
  ];
}
