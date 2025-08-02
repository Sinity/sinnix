# Automation Domain Module - Entry Point
# Complete orchestration (services + scripts)
# Consolidates: scripts, services, monitoring, scheduling

{ ... }:
{
  imports = [
    ./service.nix
    ./script.nix
    ./storage.nix
    ./cloud-optimize.nix
  ];

  config = {
    system.nixos.tags = [ "automation-domain-v0.3" ];
  };
}
