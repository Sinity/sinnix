# Per-host NixOS module list + specialArgs.
#
# Direct system builds and Colmena use the same unevaluated module lists.
# Colmena cannot use system.build.toplevel as a module: a derivation is a
# store path, not module configuration.
{ inputs }:
let
  libContext = import ./lib-context.nix { inherit inputs; };
  inherit (libContext) extendedLib mkBaseModules mkSharedSpecialArgs;

  baseModules = mkBaseModules inputs;

  # Stamp the running generation with the sinnix repo commit so
  # `nixos-version --configuration-revision` supports the live-drift
  # tripwire (AGENTS.md). Without this it falls back to the NIXPKGS
  # revision, which reads like a plausible sinnix commit and invites a wrong
  # drift diagnosis. A devshell switch builds its immutable evaluated source,
  # which lacks Git metadata, and passes that source's evaluated revision.
  # Builds from a dirty tree get the `<rev>-dirty` marker; treat that as
  # "commits since <rev> may or may not be live".
  revisionModule = {
    system.configurationRevision =
      let
        shellRevision = builtins.getEnv "SINNIX_ACTIVATION_SOURCE_REV";
      in
      if shellRevision != "" then shellRevision else inputs.self.rev or inputs.self.dirtyRev or "unknown";
  };
in
{
  inherit extendedLib;

  # Same specialArgs every host is evaluated with directly (mkFeatureModule,
  # mkServiceModule, helpers.data, and the sinnix-extended `lib`).
  specialArgs = mkSharedSpecialArgs inputs // {
    lib = extendedLib;
    # Pure public evaluation receives no private declarations. The activation
    # wrappers set SINNIX_SECRET_DECLARATIONS to the established private
    # agenix manifest and evaluate impurely.
    secretDeclarations = import ./secret-declarations.nix { };
  };

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
