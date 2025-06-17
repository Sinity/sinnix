# Automation Domain Module - Entry Point
# Complete orchestration (services + scripts)
# Consolidates: scripts, services, monitoring, scheduling

{ ... }:
{
  imports = [
    ./hyprland-scripts.nix
    ./knowledge-scripts.nix
    ./media-scripts.nix
    ./utility-scripts.nix
    ./vm-scripts.nix
    ./services.nix
    ./monitoring.nix
    ./observability.nix
  ];

  config = {
    system.nixos.tags = [ "automation-domain-v0.3" ];
  };
}
