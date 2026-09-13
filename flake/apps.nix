# CLI applications for nixos-config
#
# Provides `nix run .#<command>` convenience wrappers.
# Only for multi-step operations or commands needing nix closure wiring.
# Don't wrap single nix commands (use nix flake check, nix fmt, nix flake update directly).

{ ... }:
{
  perSystem =
    {
      pkgs,
      sinnixCommandRegistry,
      self',
      ...
    }:
    let
      commandRegistry = sinnixCommandRegistry;

      generatedApps =
        builtins.mapAttrs
          (name: spec: {
            type = "app";
            program = "${commandRegistry.mkAppCommand name spec}/bin/${name}";
            meta.description = spec.description;
          })
          (
            pkgs.lib.filterAttrs (
              name: _: !builtins.hasAttr name commandRegistry.activationPackages
            ) commandRegistry.appCommands
          );
      activationApps = builtins.mapAttrs (name: package: {
        type = "app";
        program = "${package}/bin/${name}";
        meta.description = commandRegistry.activationCommands.${name}.description;
      }) commandRegistry.activationPackages;
    in
    {
      apps =
        generatedApps
        // activationApps
        // {
          default = self'.apps.switch;
        };
    };
}
