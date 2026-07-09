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
      modules = baseModules ++ [
        # Stamp the running generation with the sinnix repo commit so
        # `nixos-version --configuration-revision` supports the live-drift tripwire
        # (CLAUDE.md). Without this it falls back to the NIXPKGS revision,
        # which reads like a plausible sinnix commit and cost a wrong drift
        # diagnosis on 2026-07-10. Builds from a dirty tree get the
        # `<rev>-dirty` marker; treat that as "commits since <rev> may or
        # may not be live".
        {
          system.configurationRevision =
            inputs.self.rev or inputs.self.dirtyRev or null;
        }
      ] ++ modules;
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
