/*
  Script registry — director only.

  All packaged scripts under `scripts/` opt in via `# @sinnix-package`
  frontmatter (description + runtimeInputs); discovery code in
  `flake/script-discovery.nix` walks the directory and constructs the
  package set.

  Scripts launched directly by Hyprland keybindings or sourced by the
  shell declare `# @sinnix-package: skip`.

  Native packages are constructed in package-set.nix. This registry chooses
  executable metadata and explicitly allows the package dependencies available
  to discovered scripts.
*/
{ inputs, pkgs }:
let
  inherit (pkgs) lib;

  externalPackages = import ./package-set.nix {
    inherit inputs pkgs;
    scorePackage = discovered.registry.sinnix-score.package;
  };
  discovery = import ./script-discovery.nix {
    inherit lib pkgs;
    siblingExtras = {
      sinnix-capture = externalPackages.sinnix-capture;
      # Importable, not executable: named by a script's `pythonPackages`
      # frontmatter, which builds that script's shebang interpreter with the
      # library on sys.path. The same `@name` resolution as runtimeInputs,
      # a different consumer.
      sinnix-lib = externalPackages.sinnix-lib;
      # Shared pairwise/choice-set preference ranking engine (rank_core);
      # consumed by scripts/sinnix-rank the same way scripts import
      # @sinnix-lib.
      sinnix-rank-core = externalPackages.sinnix-rank-core;
      # sinnix-phone-dispatcher moved out of scripts/ into a real Python
      # package (sinnix-svvz); scripts/sinnix-phone still names
      # @sinnix-phone-dispatcher in its own runtimeInputs and resolves here.
      sinnix-phone-dispatcher = externalPackages.sinnix-phone-dispatcher;
      sinnix-phone-keyguard = externalPackages.sinnix-phone-keyguard;
      # Sinnix's bd, not nixpkgs'. A script naming bare `beads` in its
      # frontmatter gets pkgs.beads (1.0.3), whose `export` has no -C flag --
      # which failed as a usage dump swallowed by `|| true`.
      beads = externalPackages.beads;
      # Native runtime and HTTP presentation are separate Python packages;
      # scripts resolve their entry points through this dependency map.
      sinnix-hub-server = externalPackages.sinnix-hub-server;
      sinnix-runtime = externalPackages.sinnix-runtime;
    };
  };
  discovered = discovery.discover (inputs.self + "/scripts");

  registry = discovered.registry // {
    sinnix-fs = {
      description = "Inspect, classify, catalog and maintain the filesystem";
      package = externalPackages.sinnix-fs;
      runtimeInputs = [ ];
      owner = "pkgs/sinnix-fs";
      docs = "docs/filesystem-index.md";
    };
    # The witness and its login helper are packaged entry points, so script
    # discovery cannot expose their existing operator commands by itself.
    sinnix-capture-xiaomi-cloud = {
      description = "Sync Xiaomi cloud band data";
      package = externalPackages.sinnix-capture-xiaomi-cloud;
      runtimeInputs = [ ];
      owner = "flake/scripts.nix";
      docs = "docs/phone.md";
    };
    sinnix-xiaomi-cloud-login = {
      description = "Authenticate the Xiaomi cloud band witness";
      package = externalPackages.sinnix-capture-xiaomi-cloud.overrideAttrs (old: {
        meta = old.meta // {
          mainProgram = "sinnix-xiaomi-cloud-login";
        };
      });
      runtimeInputs = [ ];
      owner = "flake/scripts.nix";
      docs = "docs/phone.md";
    };
  };
  scriptPackages = lib.mapAttrs (_: v: v.package) registry // {
    # Generated meta-CLI entry point over every packaged script above. Kept
    # in scriptPackages (not externalPackages) because it is derived
    # entirely from `registry`, not from an external flake input.
    sinnix = import ./cli-dispatcher.nix { inherit lib pkgs registry; };
  };

  packageSet = scriptPackages // externalPackages;
in
{
  packages = scriptPackages // {
    inherit (externalPackages) sinnix-agent-environment-doc sinnix-agent-cli-locks;
  };
  inherit packageSet;
  inherit registry;
  list = lib.attrNames registry;
}
