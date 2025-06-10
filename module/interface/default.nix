# Interface Domain Module - Entry Point
# Complete UI experience (system + desktop)
# Consolidates: desktop environment, themes, terminal, compositor

{ ... }:
{
  imports = [
    ./system.nix
    ./hyprland.nix
    ./desktop.nix
  ];

  config = {
    system.nixos.tags = [ "interface-domain-v0.3" ];
  };
}
