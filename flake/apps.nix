# CLI applications for nixos-config
#
# This module defines system-wide CLI commands that can be run
# with `nix run .#<command>`. These commands provide convenient
# access to common operations without having to enter the dev shell.

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
      # CLI applications
      apps = {
        # Default app: check configuration
        default = self'.apps.check;

        # Validate NixOS configuration
        check = mkApp "check" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          echo "Checking NixOS configuration at $flake_dir..."
          ${pkgs.nix}/bin/nix flake check --no-build "$flake_dir"
          echo "Configuration check complete!"
        '' "Validate NixOS configuration syntax and structure";

        # Format Nix files
        format = mkApp "format" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          echo "Formatting Nix files in $flake_dir..."
          ${pkgs.findutils}/bin/find "$flake_dir" -name "*.nix" -type f -not -path "*/nix/store/*" -print0 | \
          ${pkgs.findutils}/bin/xargs -0 -P 4 -I{} ${pkgs.nixfmt-rfc-style}/bin/nixfmt {}
          echo "Formatting complete!"
        '' "Format Nix files according to the RFC style";

        # Lint Nix files
        lint = mkApp "lint" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          echo "Linting Nix files in $flake_dir..."
          cd "$flake_dir"
          ${pkgs.statix}/bin/statix check

          echo "Running shellcheck on shell helpers..."
          ${pkgs.fd}/bin/fd -t f -e sh -x ${pkgs.shellcheck}/bin/shellcheck {}
          ${pkgs.fd}/bin/fd -t f -g 'scripts/*' -x ${pkgs.shellcheck}/bin/shellcheck {}

          echo "Linting complete!"
        '' "Lint Nix and shell files without modifying sources";

        # Test configuration without applying
        test = mkApp "test" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run $flake_dir#test')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild test --flake "$flake_dir#sinnix-prime" \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '' "Test configuration without applying it to the system";

        # Apply configuration to system
        switch = mkApp "switch" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run $flake_dir#switch')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake "$flake_dir#sinnix-prime" \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '' "Apply configuration changes to the system";

        # Update flake dependencies
        update = mkApp "update" ''
          flake_dir="''${PRJ_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
          echo "Updating flake inputs for $flake_dir..."
          ${pkgs.nix}/bin/nix flake update "$flake_dir"
          echo "Flake inputs updated. Run 'sudo nix run $flake_dir#switch' to apply."
        '' "Update flake dependencies to their latest versions";

        # Clean up old generations
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
