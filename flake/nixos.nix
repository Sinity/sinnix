# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
{
  flake = {
    # Define available NixOS configurations
    nixosConfigurations.sinnix-prime = inputs.nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";

      # Import modules in priority order
      modules = [
        # Enable agenix for secret management
        inputs.agenix.nixosModules.default

        # Load overlays first to make packages available everywhere
        ../module/system/overlays.nix

        # Import host-specific configuration
        { imports = [ ../host/sinnix-prime ]; }

        # Import all system modules
        { imports = [ ../module/system/default.nix ]; }
      ];

      # Make these values available to all modules
      specialArgs = {
        host = "sinnix-prime";
        username = "sinity";
        inherit inputs;

        # Provide compiled packages directly
        intercept-bounce = inputs.intercept-bounce.packages.x86_64-linux.default;
      };
    };
  };
}
