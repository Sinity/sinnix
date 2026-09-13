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
      # Helper to create runnable commands
      mkApp = name: command: description: {
        type = "app";
        program =
          (pkgs.writeShellScriptBin name ''
            set -euo pipefail
            ${command}
          '').outPath
          + "/bin/"
          + name;
        meta.description = description;
      };

      commandRegistry = sinnixCommandRegistry;

      generatedApps = builtins.mapAttrs (name: spec: mkApp name spec.script spec.description) (
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
