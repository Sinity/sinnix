# Dev shell configuration for nixos-config
#
# Integrates devenv.sh with git-hooks.nix for:
# - Automatic hook installation on shell entry
# - Development tools and Nix helpers
# - Cachix integration

{ inputs, ... }:
{
  perSystem =
    { config, pkgs, system, ... }:
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
              lspRootLauncher = import ../modules/lib/lsp-root.nix { inherit pkgs; };

              # Git hooks from git-hooks.nix flake-parts module
              gitHooksShellHook = config.pre-commit.installationScript;
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

                # Nix tools
                nil
                nixd

                # Secret management
                inputs.agenix.packages.${system}.default

                # Utilities
                nix-output-monitor
                jq
                yq
                fd
                ripgrep
                lspRootLauncher
              ]
              # Add packages required by git-hooks
              ++ config.pre-commit.settings.enabledPackages;

              # Disable devenv's built-in git-hooks (using git-hooks.nix instead)
              git-hooks.enable = false;

              # Binary cache setup
              cachix.enable = true;
              cachix.pull = [
                "sinity"
                "nix-community"
              ];

              # Helper scripts available in the shell
              scripts = {
                # Check configuration syntax and structure
                check.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#check
                '';

                # Run code quality checks (without modifying files)
                lint.exec = ''
                  ${pkgs.nix}/bin/nix develop -c pre-commit run --all-files
                '';

                # Format code according to standard (via treefmt)
                format.exec = ''
                  ${pkgs.nix}/bin/nix fmt
                '';

                # Build and apply the system configuration
                rebuild.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#switch
                '';
              };

              # Shell entry - install git hooks and show welcome message
              enterShell = ''
                # Install git hooks via git-hooks.nix
                ${gitHooksShellHook}

                echo ""
                echo "NixOS Configuration Development Environment"
                echo ""
                echo "Available commands:"
                echo "  check   - Validate configuration syntax and structure"
                echo "  format  - Apply code formatting (nix fmt via treefmt)"
                echo "  lint    - Run pre-commit hooks on all files"
                echo "  rebuild - Apply configuration to system (requires sudo)"
                echo ""
              '';
            }
          )
        ];
      };

    };
}
