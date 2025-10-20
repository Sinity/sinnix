# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
{
  flake = {
    # Define available NixOS configurations
    nixosConfigurations.sinnix-prime =
      let
        lib = inputs.nixpkgs.lib;
        sinexModule = inputs.sinex.nixosModules.default;
      in
      inputs.nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";

        # Import modules in priority order
        modules =
          [
            # Enable agenix for secret management
            inputs.agenix.nixosModules.default

            # Enable stylix for system-wide theming
            inputs.stylix.nixosModules.stylix
            # Import system-wide overlay
            (import ./overlay.nix)

            # Import domain modules directly (single-host setup)
            {
              imports = [
                ../modules/core.nix
                ../modules/programs.nix
                ../modules/logging.nix
                ../modules/secrets.nix
                ../modules/home-manager.nix
                ../modules/users.nix
                ../modules/ui.nix
                ../modules/nix-ld.nix
                ../modules/audio.nix
                ../modules/networking.nix
                ../modules/storage.nix
              ];
            }

            # Import host-specific configuration last so it can override shared defaults
            { imports = [ ../hosts/sinnix-prime ]; }
          ]
          ++ [ sinexModule ];

      # Make these values available to all modules
      specialArgs = {
        inherit inputs;
      };
    };
  };
}
