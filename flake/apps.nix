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
      mkApp = name: command: {
        type = "app";
        program =
          (pkgs.writeShellScriptBin name ''
            set -euo pipefail
            ${command}
          '').outPath
          + "/bin/"
          + name;
      };
    in
    {
      # CLI applications
      apps = {
        # Default app: check configuration
        default = self'.apps.check;

        # Validate NixOS configuration
        check = mkApp "check" ''
          echo "Checking NixOS configuration..."
          ${pkgs.nix}/bin/nix flake check --no-build
          find . -name "*.nix" -type f -print0 | xargs -0 -n1 ${pkgs.nix}/bin/nix-instantiate --parse >/dev/null
          echo "Configuration check complete!"
        '';

        # Format Nix files
        format = mkApp "format" ''
          echo "Formatting Nix files..."
          ${pkgs.findutils}/bin/find . -name "*.nix" -type f -not -path "*/nix/store/*" -print0 | \
          ${pkgs.findutils}/bin/xargs -0 -P 4 -I{} ${pkgs.nixfmt-rfc-style}/bin/nixfmt {}
          echo "Formatting complete!"
        '';

        # Lint Nix files
        lint = mkApp "lint" ''
          echo "Linting Nix files..."
          ${pkgs.statix}/bin/statix check
          echo "Linting complete!"
        '';

        # Test configuration without applying
        test = mkApp "test" ''
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run .#test')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild test --flake .#desktop \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '';

        # Apply configuration to system
        switch = mkApp "switch" ''
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run .#switch')"
            exit 1
          fi
          ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake .#desktop \
            --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
        '';

        # Update flake dependencies
        update = mkApp "update" ''
          echo "Updating flake inputs..."
          ${pkgs.nix}/bin/nix flake update
          echo "Flake inputs updated. Run 'sudo nix run .#switch' to apply."
        '';

        # Clean up old generations
        clean = mkApp "clean" ''
          if [ "$(id -u)" -ne 0 ]; then
            echo "Error: This command must be run as root (use 'sudo nix run .#clean')"
            exit 1
          fi
          echo "Removing old system generations..."
          nix-env --delete-generations old --profile /nix/var/nix/profiles/system

          echo "Optimizing nix store..."
          nix store optimise

          echo "Collecting garbage..."
          nix store gc

          echo "System cleanup complete."
        '';

        # Secret management
        agenix = mkApp "agenix" ''
          ${inputs.agenix.packages.${system}.default}/bin/agenix "$@"
        '';
      };
    };
}
