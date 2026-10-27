{
  description = "Sinity's nixos configuration";

  nixConfig = {
    extra-substituters = [
      "https://numtide.cachix.org"
      # cache.nixos.org does not reliably serve CUDA builds (ollama-cuda,
      # llama-cpp with cudaSupport); this cache turns
      # those nvcc compiles into downloads. See flake/overlay/package/local-ai.nix.
      "https://cache.nixos-cuda.org"
    ];
    extra-trusted-public-keys = [
      "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
      "cache.nixos-cuda.org:74DUi4Ye579gUqzH4ziL9IyiJBlDpMRn9MBN8oNan9M="
    ];
    # Do not bake workstation-local parallelism throttles into repository-level
    # flake config; the host owns containment policy.
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Same branch as `nixpkgs`, but deliberately NOT `follows`-ed and excluded
    # from routine `update` (flake/dev-shell.nix). Feeds the CUDA package set
    # (flake/overlay/package/local-ai.nix), so routine updates never move the
    # CUDA derivations. Bump deliberately (`sinnix update nixpkgs-ai`) to a
    # revision cache.nixos-cuda.org has built, or CUDA compiles locally.
    nixpkgs-ai.url = "github:NixOS/nixpkgs/nixos-unstable";

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
      inputs.devshell.inputs.nixpkgs.follows = "nixpkgs";
      inputs.rust-overlay.inputs.nixpkgs.follows = "nixpkgs";
    };

    scribe-tap = {
      url = "github:Sinity/scribe-tap/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Retain the Python API, service modules and gateway contracts until cutover.
    # Lynchpin follows this same predecessor source below.
    polylogue = {
      url = "github:Sinity/polylogue/3ee97894b0fed6d614fcb658e823da77c1255639";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # The Rust rewrite, run live beside the retained Python stack by
    # modules/services/polylogue.nix until consumers cut over. It keeps its
    # own nixpkgs: its shared crates need a newer rustc than Sinnix's.
    polylogue-rewrite.url = "github:Sinity/polylogue/bf685712852fb7c702fc7fe6245b39d299f812b9";

    # Private repo — fetch via HTTPS through the local gh/git credential helper.
    yt-polisher = {
      url = "git+https://github.com/Sinity/yt-polisher.git?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    lynchpin = {
      url = "git+https://github.com/Sinity/sinity-lynchpin.git?ref=master";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.polylogueSrc.follows = "polylogue";
      inputs.nixpkgsRepomix.follows = "nixpkgs";
    };

    # The phone app, extracted to its own repo (operator decision,
    # sinnix-svvz Phase 4). Sourced from GitHub like sinex/polylogue so
    # deploys follow pushed history; non-flake — sinnix's flake/scripts.nix
    # calls its pkg.nix directly, same pattern as beads.
    phone-app = {
      url = "github:Sinity/sinnix-phone-app/b93cd0d82863c9fade5cab35e17b5ee2486ae0f6";
      flake = false;
    };

    # Sinex: its package and NixOS module (modules/services/sinex/bridge.nix).
    # Pinned to a master revision; a bump is a deploy, and sinexd is restarted
    # by hand afterwards.
    #
    # nixpkgs is deliberately NOT `follows`: Sinex builds against its own
    # locked nixpkgs and Rust toolchain, so a Sinnix nixpkgs bump does not
    # rebuild it, and a Sinex revision is compiled at most once and substituted
    # from sinity.cachix.org thereafter. The desktop populates that cache:
    # `switch` publishes the Sinex closure after a successful activation
    # (sinexCachePush in flake/command-registry.nix), and the
    # sinex-cache-prebuild timer builds a newly pinned revision ahead of it.
    sinex.url = "git+https://github.com/Sinity/sinex?ref=master&rev=a081818b6ed332ac1ec7f593c97a63c48b43a61b";

    # BTRFS rollback impermanence (see modules/persistence.nix)
    impermanence = {
      url = "github:nix-community/impermanence";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # System-wide theming (fonts + cursor only; color authority is Noctalia)
    stylix.url = "github:danth/stylix";
    stylix.inputs.nixpkgs.follows = "nixpkgs";
    stylix.inputs.flake-parts.follows = "flake-parts";

    # Wayland desktop shell (Quickshell/Qt). Owns bar, launcher, notifications,
    # lock, OSD, and wallpaper, and acts as the live Material-You color authority
    # (wallpaper -> palette -> app templates). See modules/features/desktop/noctalia.nix.
    noctalia = {
      url = "github:noctalia-dev/noctalia-shell/v5.0.1";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # VSCode extensions overlay (community-maintained)
    nix-vscode-extensions.url = "github:nix-community/nix-vscode-extensions";
    nix-vscode-extensions.inputs.nixpkgs.follows = "nixpkgs";

    # Beads (`bd`) durable issue tracker for coding-agent work memory.
    # Unpinned deliberately: tracks the default branch so `nix flake update
    # beads` picks up releases without a manual version bump.
    beads = {
      url = "github:gastownhall/beads";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Declarative Android state managed from the workstation over adb.
    nix-android = {
      url = "github:devindudeman/nix-android";
      inputs.nixpkgs.follows = "nixpkgs";
      # Its flake module is required by android-rebuild; share the package
      # source without removing that module or its development dependencies.
      inputs.devenv.inputs.nixpkgs.follows = "nixpkgs";
    };

    # Declarative userland inside the Nix-on-Droid app. Termux remains the
    # Android integration and SSH host; this input owns CLI package state.
    # Retain its upstream bootstrap pin: login defaults reference exact
    # proot store paths from that package set. Its documentation output also
    # explicitly imports nixpkgs-docs with nmd; preserve that declared set.
    nix-on-droid = {
      url = "github:nix-community/nix-on-droid";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.home-manager.follows = "home-manager";
    };

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
      inputs.nixos-stable.follows = "nixpkgs";
    };

    # colmena: declarative multi-host deploy with per-host gating.
    colmena = {
      url = "github:zhaofengli/colmena";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.flake-utils.follows = "flake-utils-for-colmena";
      inputs.stable.follows = "nixpkgs";
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
        ./flake/script-registry.nix
        ./flake/command-registry-module.nix
        ./flake/dev-shell.nix
        ./flake/apps.nix
        ./flake/packages.nix
        ./flake/android.nix
        ./flake/nix-on-droid.nix
        ./flake/treefmt.nix
        ./flake/nixos.nix
        ./flake/router.nix
        ./flake/tests.nix
        ./flake/deploy.nix
      ];
    };
}
