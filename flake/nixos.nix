# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  featureLib = import ../modules/lib/features.nix { inherit lib; };
  baseModules = [
    inputs.agenix.nixosModules.default
    inputs.stylix.nixosModules.stylix
    inputs.sinex.nixosModules.default
    inputs.polylogue.nixosModules.default
    (import ./overlay)
  ];
  sharedSpecialArgs = {
    inherit inputs;
    inherit (featureLib) mkFeatureModule;
    helpers = {
      inherit (featureLib) mkDotsSymlink;
    };
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
