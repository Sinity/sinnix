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

    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Custom tools and integrations (prefer local clones under /realm/project)
    intercept-bounce = {
      url = "git+file:///realm/project/intercept-bounce?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    scribe-tap = {
      url = "git+file:///realm/project/scribe-tap?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    polylogue = {
      url = "git+file:///realm/project/polylogue?ref=master";
    };

    # Private Sinex repository stored locally; build fails fast if missing.
    sinex = {
      url = "git+file:///realm/project/sinex?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.agenix.follows = "agenix";
    };

    # BTRFS rollback impermanence (see modules/persistence.nix)
    impermanence.url = "github:nix-community/impermanence";

    # System-wide theming
    stylix.url = "github:danth/stylix";
    stylix.inputs.nixpkgs.follows = "nixpkgs";

    # VSCode extensions overlay (community-maintained)
    nix-vscode-extensions.url = "github:nix-community/nix-vscode-extensions";
    nix-vscode-extensions.inputs.nixpkgs.follows = "nixpkgs";

    nix-ai-tools.url = "github:numtide/nix-ai-tools";

    # aw-server-rust with heartbeat fix (PR #555)
    aw-server-rust = {
      url = "github:Sinity/aw-server-rust/fix/heartbeat-replace-event-id-mismatch";
      flake = false;
    };

    # Code formatting (multi-formatter via flake-parts)
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" ];
      imports = [
        # 3rd-party flake-parts modules
        inputs.treefmt-nix.flakeModule

        # Local modules
        ./flake/dev-shell.nix
        ./flake/apps.nix
        ./flake/packages.nix
        ./flake/treefmt.nix
        ./flake/nixos.nix
        ./flake/router.nix
        ./flake/tests.nix
      ];
    };
}
