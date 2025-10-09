{ ... }:
{
  imports = [
    ./core.nix
    ./desktop/hyprland.nix
    ./desktop/apps.nix
    ./desktop/display.nix
    ./desktop/environment.nix
    ./desktop/services.nix
    ./desktop/terminal.nix
    ./desktop/quickshell.nix
    ./dev/default.nix
    ./media.nix
    ./networking.nix
    ./automation/services.nix
    ./storage.nix
  ];
}
