# Per-host NixOS module list + specialArgs.
#
# Shared verbatim between the direct system build (flake/nixos.nix ->
# flake.nixosConfigurations, used by `switch`/`nix build`) and colmena's
# steady-state hive (flake/deploy.nix, used by `apply-all`). Colmena needs
# the actual unevaluated module list for each host — not a realized
# `system.build.toplevel` closure. Importing a built derivation as a module
# forces an IFD build and then fails during module merging (the derivation
# attrset coerces to its store path string where a NixOS module is expected,
# throwing "you're trying to define a value of type `string' rather than an
# attribute set"). See sinnix-bw5.
{ inputs }:
let
  libContext = import ./lib-context.nix { inherit inputs; };
  inherit (libContext) extendedLib mkBaseModules mkSharedSpecialArgs;

  baseModules = mkBaseModules inputs;

  # Stamp the running generation with the sinnix repo commit so
  # `nixos-version --configuration-revision` supports the live-drift
  # tripwire (CLAUDE.md). Without this it falls back to the NIXPKGS
  # revision, which reads like a plausible sinnix commit and cost a wrong
  # drift diagnosis on 2026-07-10. Builds from a dirty tree get the
  # `<rev>-dirty` marker; treat that as "commits since <rev> may or may not
  # be live".
  revisionModule = {
    system.configurationRevision =
      inputs.self.rev or inputs.self.dirtyRev or "unknown";
  };
in
{
  inherit extendedLib;

  # Same specialArgs every host is evaluated with directly (mkFeatureModule,
  # mkServiceModule, helpers.data, and the sinnix-extended `lib`).
  specialArgs = mkSharedSpecialArgs inputs // { lib = extendedLib; };

  hosts = {
    sinnix-prime = baseModules ++ [
      revisionModule
      ../modules/default.nix
      { imports = [ ../hosts/sinnix-prime ]; }
    ];

    sinnix-ethereal = baseModules ++ [
      revisionModule
      inputs.disko.nixosModules.disko
      ../modules/default.nix
      { imports = [ ../hosts/sinnix-ethereal ]; }
    ];
  };
}
