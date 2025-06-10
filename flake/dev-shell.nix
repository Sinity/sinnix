# Dev shell configuration for nixos-config
#
# This module defines the development environment for working
# with the NixOS configuration. It integrates devenv.sh to provide:
#
# - Git hooks for code quality
# - Development tools
# - Quality assurance scripts
# - Completions and helpers

{ inputs, ... }:
{
  perSystem =
    { pkgs, system, ... }:
    {
      # Development environment with devenv.sh
      # Note: Requires use flake . --no-pure-eval in .envrc for directory detection
      devShells.default = inputs.devenv.lib.mkShell {
        inherit inputs pkgs;
        modules = [
          {
            # Basic shell information
            name = "nixos-config-dev";

            # Set root directory for devenv
            devenv.root = "${./.}";

            # Disable task output to reduce noise
            tasks."devenv:enterShell".after = [ ];
            devenv.flakesIntegration = true;

            # Environment variables
            env.GITHUB_TOKEN = builtins.getEnv "GITHUB_TOKEN";
            env.DEVENV_TASKS_QUIET = "1";

            # Development packages
            packages = with pkgs; [
              # Version control
              git
              gh
              delta

              # Nix tools
              nixfmt-rfc-style
              nil
              nixd
              deadnix

              # Secret management
              inputs.agenix.packages.${system}.default

              # Utilities
              nix-output-monitor
              jq
              yq
              fd
              ripgrep
            ];

            # Git hooks configuration (renamed from pre-commit)
            git-hooks.hooks = {
              nixfmt-rfc-style.enable = true;
              deadnix.enable = true;
              shellcheck.enable = true;
              statix.enable = false;
            };

            # Binary cache setup
            cachix.enable = true;
            cachix.pull = [ "nix-community" ];

            # Helper scripts available in the shell
            scripts = {
              # Check configuration syntax and structure
              check.exec = ''
                ${pkgs.nix}/bin/nix flake check --no-build
                find . -name "*.nix" -type f -print0 | xargs -0 -n1 ${pkgs.nix}/bin/nix-instantiate --parse >/dev/null
              '';

              # Format Nix code according to standard
              format.exec = ''
                ${pkgs.findutils}/bin/find . -name "*.nix" -type f -not -path "*/nix/store/*" -print0 | \
                ${pkgs.findutils}/bin/xargs -0 -P 4 -I{} ${pkgs.nixfmt-rfc-style}/bin/nixfmt {}
              '';

              # Build and apply the system configuration
              rebuild.exec = ''
                if [ "$(id -u)" -ne 0 ]; then
                  echo "Error: This command must be run as root (use 'sudo')"
                  exit 1
                fi
                ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake .#sinnix-prime \
                  --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
              '';
            };

            # Welcome message with available commands
            enterShell = ''
              echo ""
              echo "NixOS Configuration Development Environment"
              echo ""
              echo "Available commands:"
              echo "  check     - Validate configuration syntax and structure"
              echo "  format    - Apply code formatting rules"
              echo "  lint      - Run code quality checks"
              echo "  rebuild   - Apply configuration to system (requires sudo)"
              echo ""
            '';
          }
        ];
      };
    };
}
