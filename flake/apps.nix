# CLI applications for nixos-config
#
# Provides `nix run .#<command>` convenience wrappers.
# Only for multi-step operations or commands needing nix closure wiring.
# Don't wrap single nix commands (use nix flake check, nix fmt, nix flake update directly).

{ inputs, ... }:
{
  perSystem =
    {
      pkgs,
      system,
      self',
      sinnixScriptRegistry,
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

      # sinnixScriptRegistry (flake/script-registry.nix) is the one
      # evaluation of scripts.nix per perSystem `pkgs`, shared via
      # `_module.args` -- not a second re-walk of scripts/ for this file.
      commandRegistry = import ./command-registry.nix {
        inherit
          inputs
          pkgs
          system
          sinnixScriptRegistry
          ;
      };

      generatedApps = builtins.mapAttrs (
        name: spec: mkApp name spec.script spec.description
      ) commandRegistry.appCommands;
    in
    {
      apps = generatedApps // {
        default = self'.apps.switch;
      };
    };
}
