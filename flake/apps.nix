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
      ...
    }:
    let
      # Resolve flake directory from PRJ_ROOT or git root
      resolveFlakeDir = ''
        _flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
      '';

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
    in
    {
      apps = {
        default = self'.apps.switch;

        # Lint Nix and shell files (deadnix + statix + shellcheck)
        lint = mkApp "lint" ''
          ${resolveFlakeDir}
          cd "$_flake_dir"
          echo "Running deadnix..."
          ${pkgs.deadnix}/bin/deadnix --fail .
          echo "Running statix..."
          ${pkgs.statix}/bin/statix check

          echo "Running shellcheck on shell helpers..."
          ${pkgs.fd}/bin/fd -t f -e sh -x ${pkgs.shellcheck}/bin/shellcheck {}
          shellcheck_targets="$(${pkgs.ripgrep}/bin/rg -Il '^#!.*\\b(bash|sh|zsh)\\b' scripts || true)"
          if [ -n "$shellcheck_targets" ]; then
            while IFS= read -r target; do
              [ -n "$target" ] && ${pkgs.shellcheck}/bin/shellcheck "$target"
            done <<<"$shellcheck_targets"
          fi

          echo "Linting complete!"
        '' "Lint Nix and shell files without modifying sources";

        # Test configuration without applying
        test = mkApp "test" ''
          ${resolveFlakeDir}
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run $_flake_dir#test')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild test --flake "$_flake_dir#sinnix-prime" \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '' "Test configuration without applying it to the system";

        # Apply configuration to system
        switch = mkApp "switch" ''
          ${resolveFlakeDir}
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run $_flake_dir#switch')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake "$_flake_dir#sinnix-prime" \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '' "Apply configuration changes to the system";

        # Clean up old generations + gc + optimize
        clean = mkApp "clean" ''
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run .#clean')"
            exit 1
          fi
          echo "Removing old system generations..."
          if ! nix profile wipe-history --profile /nix/var/nix/profiles/system --older-than 30d >/dev/null 2>&1; then
            echo "nix profile wipe-history unavailable, falling back to nix-env"
            nix-env --delete-generations old --profile /nix/var/nix/profiles/system
          fi

          echo "Optimizing nix store..."
          nix store optimise

          echo "Collecting garbage..."
          nix store gc

          echo "System cleanup complete."
        '' "Clean up old system generations and optimize nix store";

        # Secret management
        agenix = mkApp "agenix" ''
          ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
        '' "Manage encrypted secrets with agenix";
      };
    };
}
