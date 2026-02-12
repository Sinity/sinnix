# Dev shell configuration for nixos-config
#
# Provides:
# - Development tools and Nix helpers
# - Cachix integration
# - Helper scripts for common operations

{ inputs, ... }:
{
  perSystem =
    {
      config,
      pkgs,
      system,
      ...
    }:
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
              # Script packages from flake registry
              scriptPkgs = inputs.self.packages.${system};
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
                scriptPkgs.lsp-root
              ];

              # Disable devenv's built-in git-hooks
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

                # Format code according to standard (via treefmt)
                format.exec = ''
                  ${pkgs.nix}/bin/nix fmt
                '';

                # Build and apply the system configuration
                rebuild.exec = ''
                  ${pkgs.nix}/bin/nix run ${resolvedRoot}#switch
                '';
              };

              # Shell entry - show welcome message
              enterShell = ''
                echo ""
                echo "NixOS Configuration Development Environment"
                echo ""
                echo "Available commands:"
                echo "  check   - Validate configuration syntax and structure"
                echo "  format  - Apply code formatting (nix fmt via treefmt)"
                echo "  rebuild - Apply configuration to system (requires sudo)"
                echo ""
              '';
            }
          )
        ];
      };

    };
}
