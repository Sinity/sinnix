# Dev shell configuration for nixos-config
#
# Provides:
# - Development tools and Nix helpers
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
    let
      scriptPkgs = inputs.self.packages.${system};

      # Helper scripts available in the dev shell
      check = pkgs.writeShellScriptBin "check" ''
        exec ${pkgs.nix}/bin/nix flake check
      '';
      format = pkgs.writeShellScriptBin "format" ''
        exec ${pkgs.nix}/bin/nix fmt
      '';
      rebuild = pkgs.writeShellScriptBin "rebuild" ''
        exec sudo ${pkgs.nix}/bin/nix run .#switch
      '';
    in
    {
      devShells.default = pkgs.mkShellNoCC {
        name = "nixos-config-dev";

        packages = [
          # Version control
          pkgs.git
          pkgs.gh
          pkgs.delta

          # Nix tools
          pkgs.nil
          pkgs.nixd

          # Secret management
          inputs.agenix.packages.${system}.default

          # Router access
          pkgs.sshpass

          # Utilities
          pkgs.nix-output-monitor
          pkgs.jq
          pkgs.yq
          pkgs.fd
          pkgs.ripgrep
          scriptPkgs.lsp-root

          # Helper scripts
          check
          format
          rebuild
        ];

        shellHook = ''
          echo ""
          echo "NixOS Configuration Development Environment"
          echo ""
          echo "Available commands:"
          echo "  check   - Validate configuration (nix flake check)"
          echo "  format  - Apply code formatting (nix fmt)"
          echo "  rebuild - Apply configuration to system (sudo nix run .#switch)"
          echo ""
        '';
      };
    };
}
