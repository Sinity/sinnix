# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  baseModules = [
    inputs.agenix.nixosModules.default
    (import ./overlay.nix)
  ];
  sinexModule = inputs.sinex.nixosModules.default;
  sharedSpecialArgs = {
    inherit inputs;
  };
in
{
  flake.nixosConfigurations = {
    sinnix-prime = lib.nixosSystem {
      system = "x86_64-linux";
      modules = baseModules ++ [
        inputs.stylix.nixosModules.stylix
        {
          imports = [
            ../modules/foundation.nix
            ../modules/core.nix
            ../modules/programs.nix
            ../modules/diagnostics.nix
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
        { imports = [ ../hosts/sinnix-prime ]; }
        sinexModule
      ];
      specialArgs = sharedSpecialArgs;
    };

    sinnix-ethereal = lib.nixosSystem {
      system = "x86_64-linux";
      modules = baseModules ++ [
        inputs.disko.nixosModules.disko
        {
          imports = [
            ../modules/foundation.nix
            ../modules/core.nix
            ../modules/logging.nix
            ../modules/secrets.nix
            ../modules/home-manager.nix
            ../modules/users.nix
          ];
        }
        { imports = [ ../hosts/sinnix-ethereal ]; }
      ];
      specialArgs = sharedSpecialArgs;
    };
  };
}
