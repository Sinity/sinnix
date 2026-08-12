# NixOS system configuration
#
# This module defines the system-level configuration for NixOS.
# It integrates core modules, system services, and specialized
# packages into a cohesive system configuration.

{ inputs, ... }:
let
  hostContext = import ./host-modules.nix { inherit inputs; };
  inherit (hostContext) extendedLib specialArgs hosts;

  mkHost =
    {
      system ? "x86_64-linux",
      modules,
    }:
    extendedLib.nixosSystem {
      inherit system modules specialArgs;
    };
in
{
  flake.nixosConfigurations = {
    sinnix-prime = mkHost {
      modules = hosts.sinnix-prime;
    };

    sinnix-ethereal = mkHost {
      modules = hosts.sinnix-ethereal;
    };
  };
}
