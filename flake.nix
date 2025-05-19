{
  description = "Sinity's nixos configuration";

  # External dependencies for the flake
  inputs = {
    # Core Nix packages - we use unstable for latest features
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    
    # Nix User Repository - community packages
    nur.url = "github:nix-community/NUR";

    # Home Manager - for user environment management
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs"; # Use the same nixpkgs as the flake
    };

    # Agenix - secret management with age encryption
    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Cached browsers for development
    browser-previews = {
      url = "github:nix-community/browser-previews";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Custom bounce intercept tool
    intercept-bounce = {
      url = "github:sinity/intercept-bounce";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Claude desktop client
    claude-desktop = {
      url = "github:k3d3/claude-desktop-linux-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Claude squad integration
    claude-squad = {
      url = "github:sinity/claude-squad/add-nix-support";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Claude code logging utility
    claude-code-logger = {
      url = "github:sinity/claude-code-logger/add-nix-support";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Pre-commit hooks management
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # Define the outputs for this flake
  outputs =
    {
      nixpkgs,
      self,
      agenix,
      intercept-bounce,
      git-hooks,
      ...
    }@inputs:
    let
      # Common variables used throughout the flake
      username = "sinity";
      system = "x86_64-linux"; # The system architecture
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      # NixOS system configuration for the desktop machine
      nixosConfigurations.desktop = nixpkgs.lib.nixosSystem {
        inherit system;

        # The modules that make up the system configuration
        modules = [
          # Setup agenix for secret management
          agenix.nixosModules.default
          # Load overlays first to make them available everywhere
          ./module/core/overlays.nix
          # Import all core modules
          ./module/core/default.nix
        ];

        # Special arguments passed to all modules
        specialArgs = {
          host = "desktop"; # Current hostname
          inherit self inputs username;
          # Provide intercept-bounce package directly
          intercept-bounce = inputs.intercept-bounce.packages.${system}.default;
        };
      };

      # Pre-commit hooks configuration for code quality
      checks.${system} = {
        pre-commit-check = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = {
            # Nix code formatting and linting tools
            nixfmt-rfc-style.enable = true; # Format Nix code according to RFC style
            statix.enable = true;           # Check for anti-patterns in Nix code
            deadnix.enable = true;          # Find and remove unused code

            # Shell script validation
            shellcheck.enable = true;       # Check shell scripts for errors
          };

          # Files to exclude from hook processing
          excludes = [
            "nvim/lazy-lock.json" # Auto-generated lock file
            "flake.lock"          # Flake lockfile (managed separately)
          ];
        };
      };

      # Development environment with all necessary tools
      devShells.${system}.default = pkgs.mkShell {
        # Tools available in the development shell
        buildInputs = with pkgs; [
          git                              # Version control
          nixfmt-rfc-style                 # Nix code formatter
          statix                           # Nix code linter
          nixd                             # Nix language server
          deadnix                          # Detect unused code
          agenix.packages.${system}.default # Secret management
          pre-commit                       # Hook manager
          nix-output-monitor               # Improved build output
        ];

        # Commands run when entering the development shell
        shellHook = ''
          # Setup pre-commit hooks automatically
          ${self.checks.${system}.pre-commit-check.shellHook}

          echo "NixOS Configuration Development Environment"
          echo ""
          echo "Available commands:"
          echo "  * nix run .#format  - Format all Nix files"
          echo "  * nix run .#lint    - Lint all Nix files"
          echo "  * nix run .#check   - Check configuration"
          echo "  * nix run .#test    - Test configuration (with nom)"
          echo "  * nix run .#switch  - Apply configuration (with nom)"
          echo "  * nix run .#update  - Update and apply configuration"
          echo "  * nix run .#clean   - Clean up old generations"
          echo "  * nix run .#agenix  - Manage secrets"
          echo ""
          # Set up nix-output-monitor for better build visualization
          export NIX_BUILD_HOOK=${pkgs.nix-output-monitor}/bin/nom-build-hook
          export NIX_BUILD_HOOK_INVOCATION_PREFIX='nom --print-build --json'
          echo "nix-output-monitor (nom) enabled for better build output"
          echo ""
        '';
      };

      # Collection of utility commands that can be run with 'nix run'
      apps.${system} =
        let
          # Base helper function to create flake apps with proper metadata
          mkApp = name: description: script: {
            type = "app";
            program = "${script}/bin/${name}";
            meta.description = description;
          };

          # Create a simple command with description and consistent error handling
          mkSimpleApp = name: description: command: 
            mkApp name description (pkgs.writeShellScriptBin name command);

          # Create a command with standard output formatting and error handling
          mkFormattedApp =
            name: desc: command:
            mkSimpleApp name desc ''
              set -euo pipefail
              echo "${desc}..."
              ${command}
              echo "${desc} complete!"
            '';
        in
        {
          # Default app (runs 'check')
          default = {
            type = "app";
            program = self.apps.${system}.check.program;
            meta.description = "Validate NixOS configuration (default command)";
          };

          # Secret management
          agenix = mkSimpleApp "run-agenix" "Manage secrets with agenix" ''
            ${agenix.packages.${system}.default}/bin/agenix "$@"
          '';

          # Test configuration (run with sudo)
          test = mkSimpleApp "nixos-test" "Test NixOS configuration without applying it" ''
            # Check if running as root
            if [ "$(id -u)" -ne 0 ]; then
              echo "Error: This command must be run as root (use 'sudo nix run .#test')"
              exit 1
            fi

            # Use nixos-rebuild with nom integration
            ${pkgs.nixos-rebuild}/bin/nixos-rebuild test --flake .#desktop \
              --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
          '';

          # Validate configuration files
          check = mkFormattedApp "validate-nix-config" "Checking NixOS configuration" ''
            echo "Checking flake and configurations..."
            ${pkgs.nix}/bin/nix flake check --no-build
            echo "Checking Nix files syntax..."
            find . -name "*.nix" -type f -print0 | xargs -0 -n1 ${pkgs.nix}/bin/nix-instantiate --parse >/dev/null
          '';

          # Format all Nix files with nice output
          format = mkFormattedApp "format-nix-files" "Formatting Nix files with nixfmt-rfc-style" ''
            echo "Formatting Nix files..."
            ${pkgs.findutils}/bin/find . -name "*.nix" -type f -not -path "*/nix/store/*" -print0 | \
            ${pkgs.findutils}/bin/xargs -0 -P 4 -I{} ${pkgs.nixfmt-rfc-style}/bin/nixfmt {} 2>&1 | \
            ${pkgs.gnused}/bin/sed 's/^/  /'
            echo "Formatting complete."
          '';

          # Run statix linter with nice output
          lint = mkFormattedApp "lint-nix-files" "Linting Nix files with statix" ''
            echo "Linting Nix files with statix..."
            # Run statix check but capture exit code
            set +e
            ${pkgs.statix}/bin/statix check
            STATIX_EXIT=$?
            set -e

            # Report outcome
            if [ $STATIX_EXIT -eq 0 ]; then
              echo "No issues found!"
            else
              echo "Issues found - see output above."
            fi
          '';

          # Apply NixOS configuration (run with sudo)
          switch = mkSimpleApp "nixos-switch" "Apply NixOS configuration changes" ''
            # Check if running as root
            if [ "$(id -u)" -ne 0 ]; then
              echo "Error: This command must be run as root (use 'sudo nix run .#switch')"
              exit 1
            fi

            # Use nixos-rebuild with nom integration
            ${pkgs.nixos-rebuild}/bin/nixos-rebuild switch --flake .#desktop \
              --log-format internal-json -v 2>&1 | ${pkgs.nix-output-monitor}/bin/nom --json
          '';

          # Update flake inputs (does not apply configuration)
          update = mkFormattedApp "nixos-update" "Updating flake inputs" ''
            # Update flake dependencies
            ${pkgs.nix}/bin/nix flake update
            echo "Flake inputs updated successfully."
            echo ""
            echo "To apply the updated configuration, run: sudo nix run .#switch"
          '';

          # Clean up old generations and storage (run with sudo)
          clean = mkFormattedApp "nixos-clean" "Collecting garbage and removing old generations" ''
            # Check if running as root
            if [ "$(id -u)" -ne 0 ]; then
              echo "Error: This command must be run as root (use 'sudo nix run .#clean')"
              exit 1
            fi

            # Remove old system generations, keeping the last 5
            echo "Removing old system generations..."
            nix-env --delete-generations old --profile /nix/var/nix/profiles/system

            # Optimize nix store
            echo "Optimizing nix store..."
            nix store optimise

            # Collect garbage
            echo "Collecting garbage..."
            nix store gc

            echo "System cleanup complete."
          '';
        };

    };
}
