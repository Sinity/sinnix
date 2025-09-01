# Interface Domain Module - Entry Point
# Complete UI experience (system + desktop)
# Consolidates: desktop environment, themes, terminal, compositor

{ ... }:
{
  imports = [
    ./system.nix
    ./hyprland.nix
    ./apps.nix
    ./display.nix
    ./environment.nix
    ./quickshell.nix
    ./services.nix
    ./terminal.nix
  ];

  config = {
    system.nixos.tags = [ "interface-domain-v0.3" ];
  };
}
