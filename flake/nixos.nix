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
    inputs.stylix.nixosModules.stylix
    (import ./overlay)
  ];
  sharedSpecialArgs = {
    inherit inputs;
  };
  mkHost =
    {
      system ? "x86_64-linux",
      modules,
    }:
    lib.nixosSystem {
      inherit system;
      modules = baseModules ++ modules;
      specialArgs = sharedSpecialArgs;
    };
in
{
  flake.nixosConfigurations = {
    sinnix-prime = mkHost {
      modules = [
        inputs.sinex.nixosModules.default
        ../modules/default.nix
        { imports = [ ../hosts/sinnix-prime ]; }
      ];
    };

    sinnix-ethereal = mkHost {
      modules = [
        inputs.disko.nixosModules.disko
        ../modules/default.nix
        { imports = [ ../hosts/sinnix-ethereal ]; }
      ];
    };
  };
}
