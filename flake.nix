{
  description = "Sinity's nixos configuration";

  nixConfig = {
    extra-substituters = [
      "https://numtide.cachix.org"
    ];
    extra-trusted-public-keys = [
      "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
    ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixpkgs-patched = {
      url = "path:./flake/nixpkgs-patched";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nur = {
      url = "github:nix-community/NUR";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs-patched";
    };

    # User environment management
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs-patched";

    # Secret management with age encryption
    agenix.url = "github:ryantm/agenix";
    agenix.inputs.nixpkgs.follows = "nixpkgs-patched";

    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    # Development tools
    devenv.url = "github:cachix/devenv";
    devenv.inputs.nixpkgs.follows = "nixpkgs-patched";

    # Custom tools and integrations
    intercept-bounce.url = "github:sinity/intercept-bounce";
    intercept-bounce.inputs.nixpkgs.follows = "nixpkgs-patched";

    scribe-tap = {
      url = "github:Sinity/scribe-tap";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    polylogue = {
      url = "github:Sinity/polylogue";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    sinevec = {
      url = "github:Sinity/sinevec";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    # Private Sinex repository; intentionally expects SSH access to the upstream
    # repository so evaluation fails cleanly when the key is missing.
    sinex = {
      url = "git+ssh://git@github.com/Sinity/sinex?ref=master";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    # System-wide theming
    stylix.url = "github:danth/stylix";
    stylix.inputs.nixpkgs.follows = "nixpkgs-patched";

    # VSCode extensions overlay (community-maintained)
    nix-vscode-extensions.url = "github:nix-community/nix-vscode-extensions";
    nix-vscode-extensions.inputs.nixpkgs.follows = "nixpkgs-patched";

    # Modern Qt/QML based desktop shell toolkit
    quickshell = {
      url = "git+https://git.outfoxxed.me/outfoxxed/quickshell";
      inputs.nixpkgs.follows = "nixpkgs-patched";
    };

    nix-ai-tools = {
      url = "github:numtide/nix-ai-tools";
      inputs.nixpkgs.follows = "nixpkgs-patched";
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
