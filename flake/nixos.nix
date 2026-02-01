# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  featureLib = import ../modules/lib/features.nix { inherit lib; };
  systemdLib = import ../modules/lib/systemd-hardening.nix { inherit lib; };
  overlayLib = import ../modules/lib/overlay-helpers.nix { inherit lib; };

  # Extend lib with sinnix helpers globally available
  extendedLib = lib.extend (final: prev: {
    sinnix = {
      inherit (featureLib) mkPAMLimits mkAutoImports mkBundleModule;
      systemd = systemdLib;
      overlay = overlayLib;
    };
  });

  baseModules = [
    inputs.agenix.nixosModules.default
    inputs.stylix.nixosModules.stylix
    inputs.sinex.nixosModules.default
    inputs.polylogue.nixosModules.default
    (import ./overlay { inherit inputs overlayLib; })
  ];
  sharedSpecialArgs = {
    inherit inputs;
    inherit (featureLib) mkFeatureModule mkServiceModule;
    helpers = {
      inherit (featureLib) mkDotsLink mkDotsFile;
    };
  };
  mkHost =
    {
      system ? "x86_64-linux",
      modules,
    }:
    extendedLib.nixosSystem {
      inherit system;
      modules = baseModules ++ modules;
      specialArgs = sharedSpecialArgs // { lib = extendedLib; };
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
