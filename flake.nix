{
  description = "Sinity's nixos configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nur.url = "github:nix-community/NUR";

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };

    # User environment management
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    # Secret management with age encryption
    agenix.url = "github:ryantm/agenix";
    agenix.inputs.nixpkgs.follows = "nixpkgs";

    # Development tools
    browser-previews.url = "github:nix-community/browser-previews";
    browser-previews.inputs.nixpkgs.follows = "nixpkgs";

    devenv.url = "github:cachix/devenv";
    devenv.inputs.nixpkgs.follows = "nixpkgs";

    # Custom tools and integrations
    intercept-bounce.url = "github:sinity/intercept-bounce";
    intercept-bounce.inputs.nixpkgs.follows = "nixpkgs";

    claude-desktop.url = "github:k3d3/claude-desktop-linux-flake";
    claude-desktop.inputs.nixpkgs.follows = "nixpkgs";

    claude-squad.url = "github:sinity/claude-squad/add-nix-support";
    claude-squad.inputs.nixpkgs.follows = "nixpkgs";

    claude-code-logger.url = "github:sinity/claude-code-logger/add-nix-support";
    claude-code-logger.inputs.nixpkgs.follows = "nixpkgs";

    sinex.url = "git+ssh://git@github.com/Sinity/sinex";
    sinex.inputs.nixpkgs.follows = "nixpkgs";

    # System-wide theming
    stylix.url = "github:danth/stylix";
    stylix.inputs.nixpkgs.follows = "nixpkgs";

    # Hyprland and plugins
    hyprland.url = "github:hyprwm/Hyprland";

    hyprland-plugins = {
      url = "github:hyprwm/hyprland-plugins";
      inputs.hyprland.follows = "hyprland";
    };
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" ];
      imports = [
        ./flake/dev-shell.nix
        ./flake/apps.nix
        ./flake/nixos.nix
      ];
    };
}
