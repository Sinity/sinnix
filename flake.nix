{
  description = "Sinity's nixos configuration";

  nixConfig = {
    extra-substituters = [
      "https://numtide.cachix.org"
    ];
    extra-trusted-public-keys = [
      "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
    ];
    # Do not bake workstation-local parallelism throttles into repository-level
    # flake config; the host owns containment policy.
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };

    # User environment management
    home-manager.url = "github:nix-community/home-manager/master";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    # Secret management with age encryption
    agenix.url = "github:ryantm/agenix";
    agenix.inputs.nixpkgs.follows = "nixpkgs";

    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    lanzaboote = {
      url = "github:nix-community/lanzaboote";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Custom tools and integrations.
    # Use GitHub-backed inputs when a canonical remote exists so system
    # deployments don't implicitly consume local checkout state.
    intercept-bounce = {
      url = "github:Sinity/intercept-bounce/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    scribe-tap = {
      url = "github:Sinity/scribe-tap/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    polylogue = {
      url = "github:Sinity/polylogue/fix/live-insight-memory-headroom";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Private repo — fetch via HTTPS through the local gh/git credential helper.
    yt-polisher = {
      url = "git+https://github.com/Sinity/yt-polisher.git?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    lynchpin = {
      url = "git+file:///realm/project/sinity-lynchpin?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.polylogueSrc.follows = "polylogue";
    };

    # Sinex is sourced from GitHub so system deployments follow pushed upstream
    # history instead of implicitly consuming the local checkout state.
    sinex = {
      url = "git+https://github.com/Sinity/sinex?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.agenix.follows = "agenix";
    };

    # BTRFS rollback impermanence (see modules/persistence.nix)
    impermanence.url = "github:nix-community/impermanence";

    # System-wide theming (fonts + cursor only; color authority is Noctalia)
    stylix.url = "github:danth/stylix";
    stylix.inputs.nixpkgs.follows = "nixpkgs";
    stylix.inputs.flake-parts.follows = "flake-parts";

    # Wayland desktop shell (Quickshell/Qt). Owns bar, launcher, notifications,
    # lock, OSD, and wallpaper, and acts as the live Material-You color authority
    # (wallpaper -> palette -> app templates). See modules/features/desktop/noctalia.nix.
    noctalia = {
      url = "github:noctalia-dev/noctalia-shell/v5";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # VSCode extensions overlay (community-maintained)
    nix-vscode-extensions.url = "github:nix-community/nix-vscode-extensions";
    nix-vscode-extensions.inputs.nixpkgs.follows = "nixpkgs";

    # Fast-moving agent CLI package supply. Keep its nixpkgs independent:
    # upstream packages are daily-updated and often expect their own pinned
    # dependency graph. Sinnix wraps/projects these tools locally instead of
    # owning their package derivations.
    llm-agents.url = "github:numtide/llm-agents.nix";

    # Code formatting (multi-formatter via flake-parts)
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # nixos-anywhere: bootstrap NixOS over SSH from a foreign initrd.
    # Used to seed sinnix-ethereal from the default Hetzner image.
    nixos-anywhere = {
      url = "github:nix-community/nixos-anywhere";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.disko.follows = "disko";
    };

    # colmena: declarative multi-host deploy with per-host gating.
    colmena = {
      url = "github:zhaofengli/colmena";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils-for-colmena";
    };

    # colmena pulls in flake-utils; pin it once here so the dep graph stays
    # de-duplicated.
    flake-utils-for-colmena = {
      url = "github:numtide/flake-utils";
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
        ./flake/deploy.nix
      ];
    };
}
