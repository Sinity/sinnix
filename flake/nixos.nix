# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
let
  libContext = import ./lib-context.nix { inherit inputs; };
  inherit (libContext) extendedLib mkBaseModules mkSharedSpecialArgs;

  baseModules = mkBaseModules inputs;
  sharedSpecialArgs = mkSharedSpecialArgs inputs;

  mkHost =
    {
      system ? "x86_64-linux",
      modules,
    }:
    extendedLib.nixosSystem {
      inherit system;
      modules = baseModules ++ modules;
      specialArgs = sharedSpecialArgs // {
        lib = extendedLib;
      };
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
