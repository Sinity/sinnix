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
          (
            let
              envRoot = builtins.getEnv "DEVENV_ROOT";
              pwd = builtins.getEnv "PWD";
              usePath = path: path != "" && builtins.match "^/nix/store/.*" path == null;
              resolvedRoot =
                if usePath envRoot then
                  envRoot
                else if usePath pwd then
                  pwd
                else
                  builtins.toString ./.;
              stateRoot =
                let
                  rootHash = builtins.substring 0 10 (builtins.hashString "sha256" resolvedRoot);
                in
                "/tmp/sinnix-devenv-" + rootHash;
            in
            {
              # Basic shell information
              name = "nixos-config-dev";

              # Set project root explicitly (prefer direnv-provided path to avoid /nix/store)
              devenv = {
                root = resolvedRoot;
                dotfile = stateRoot;
                tmpdir = "${stateRoot}/tmp";
              };

              # Disable task output to reduce noise
              tasks."devenv:enterShell".after = [ ];
              devenv.flakesIntegration = true;
              dotenv.disableHint = true;

              # Environment variables
              env.GITHUB_TOKEN = builtins.getEnv "GITHUB_TOKEN";
              env.DEVENV_TASKS_QUIET = "1";

              # Development packages
              packages = with pkgs; [
                # Version control
                git
                gh
                delta
                pre-commit

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

              # Disable devenv-managed git hooks; use the committed
              # `.pre-commit-config.yaml` for manual `pre-commit` usage instead.
              git-hooks = {
                enable = false;
                hooks = { };
              };

              # Binary cache setup
              cachix.enable = true;
              cachix.pull = [ "sinity" "nix-community" ];

              # Helper scripts available in the shell
              scripts = {
                # Check configuration syntax and structure
                check.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#check
                '';

                # Run code quality checks (without modifying files)
                lint.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#lint
                '';

                # Format Nix code according to standard
                format.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#format
                '';

                # Build and apply the system configuration
                rebuild.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#switch
                '';
              };

              # Welcome message with available commands
              enterShell = ''
                  # Ensure devenv git-hooks state config is valid JSON
                GH_STATE_DIR="${stateRoot}/state/git-hooks"
                GH_CFG="$GH_STATE_DIR/config.json"
                  if [ ! -e "$GH_CFG" ] || ! ${pkgs.jq}/bin/jq . "$GH_CFG" >/dev/null 2>&1; then
                    mkdir -p "$GH_STATE_DIR"
                    printf '%s\n' '{"configPath": ".pre-commit-config.yaml"}' > "$GH_CFG"
                  fi

                  echo ""
                  echo "NixOS Configuration Development Environment"
                  echo ""
                  echo "Available commands:"
                  echo "  check     - Validate configuration syntax and structure"
                  echo "  format    - Apply code formatting rules"
                  echo "  lint      - Run code quality checks"
                  echo "  rebuild   - Apply configuration to system (requires sudo)"
                  echo "  pre-commit install - Activate repo git hooks"
                  echo ""
              '';
            }
          )
        ];
      };

    };
}
