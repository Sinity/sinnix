{ lib }:
let
  # Generate sub-feature options from declarative spec
  # subFeatures = { name = { description = "..."; default = false; }; ... }
  mkSubFeatureOptions =
    subFeatures:
    lib.mapAttrs (name: spec: {
      enable = (lib.mkEnableOption (spec.description or name)) // {
        default = spec.default or false;
      };
    }) subFeatures;

  # Static capability metadata slot. Consumed by sweep modules
  # (modules/dotfiles-sweep.nix, etc.) to centralize cross-cutting concerns.
  # Currently used for:
  #   meta.dotfiles.configFile = { "rel/in/xdg" = "rel/in/dots"; ... };
  #   meta.dotfiles.dataFile = { ... };
  # Entries may be strings (simple recursive symlink) or attrsets with
  # source/recursive/force/onChange keys (full HM file declaration).
  mkMetaOption =
    metaValue:
    lib.mkOption {
      type = lib.types.attrsOf lib.types.unspecified;
      default = metaValue;
      description = "Static capability metadata consumed by sweep modules.";
      internal = true;
    };

  mkFeatureModule =
    {
      path,
      description,
      extraOptions ? { },
      # Declarative sub-features
      # subFeatures = { vscode = { description = "VSCode"; default = true; }; ... }
      subFeatures ? { },
      meta ? { },
      # Features are default-ON by contract (see comment below). defaultOn is
      # an explicit escape hatch, not routine per-module tuning; optional
      # background capabilities normally belong in the default-off service
      # namespace instead.
      defaultOn ? true,
      configFn,
    }:
    args@{ config, ... }:
    let
      featurePath = [
        "sinnix"
        "features"
      ]
      ++ path;
      # Merge extraOptions with generated sub-feature options.
      # Use a recursive merge so nested attrs like `factorio.username`
      # coexist with generated `factorio.enable`.
      subFeatureOpts = mkSubFeatureOptions subFeatures;
      # Features sitting in modules/features/ are unconditionally part of a
      # sinnix host's default character. Hosts express exceptions via
      # `sinnix.features.<path>.enable = false;`. Capabilities that are not
      # part of the normal interactive character should be default-off
      # services or omitted from the active module tree.
      #
      # extraOptions must not define its own top-level `enable`: the `//`
      # merge below replaces it wholesale, silently discarding whatever a
      # caller declared there (sinnix-tgy, 2026-07-08 — a module comment
      # claimed "disabled by default" via extraOptions.enable while this
      # factory forced enable.default=true underneath it, unnoticed).
      optionsForPath =
        if extraOptions ? enable then
          throw "mkFeatureModule ${builtins.concatStringsSep "." path}: extraOptions must not define 'enable' (generated automatically, default = ${lib.boolToString defaultOn}); use the defaultOn argument instead"
        else
          lib.recursiveUpdate extraOptions subFeatureOpts
          // {
            enable = (lib.mkEnableOption description) // {
              default = defaultOn;
            };
            meta = mkMetaOption meta;
          };
      cfg = lib.getAttrFromPath featurePath config;
      user = config.sinnix.user.name;
    in
    {
      options = lib.setAttrByPath featurePath optionsForPath;
      config = lib.mkIf cfg.enable (configFn (args // { inherit cfg user; }));
    };

  # Service module factory - like mkFeatureModule but for sinnix.services.*
  # Services typically don't need `user` passed (they use config.sinnix.user.name directly)
  mkServiceModule =
    {
      name,
      description,
      extraOptions ? { },
      surface ? null,
      meta ? { },
      configFn,
    }:
    args@{ config, lib, ... }:
    let
      servicePath = [
        "sinnix"
        "services"
        name
      ];
      optionsForPath = extraOptions // {
        enable = lib.mkEnableOption description;
        meta = mkMetaOption meta;
      };
      cfg = lib.getAttrFromPath servicePath config;
    in
    {
      options = lib.setAttrByPath servicePath optionsForPath;
      config = lib.mkIf cfg.enable (
        lib.mkMerge [
          (lib.optionalAttrs (surface != null) {
            sinnix.runtime.surfaces.${name} = surface;
          })
          (configFn (args // { inherit cfg; }))
        ]
      );
    };

  # Pre-curried version for extraSpecialArgs - eliminates boilerplate in modules
  # Usage in home-manager.nix extraSpecialArgs:
  #   mkDotsFileFor = helpers.mkDotsFileFor config.sinnix;
  # Then in HM modules:
  #   { config, mkDotsFileFor, ... }: let mkDotsFile = mkDotsFileFor config; in { ... }
  mkDotsFileFor =
    sinnix: hmConfig: rel:
    hmConfig.lib.file.mkOutOfStoreSymlink (sinnix.paths.dotsRoot + rel);

  # PAM login limits factory
  # Usage: mkPAMLimits { domain = "@audio"; rtprio = 95; memlock = "unlimited"; }
  mkPAMLimits =
    {
      domain,
      rtprio ? null,
      memlock ? null,
      nice ? null,
    }:
    lib.concatLists [
      (lib.optional (rtprio != null) {
        inherit domain;
        type = "-";
        item = "rtprio";
        value = toString rtprio;
      })
      (lib.optional (memlock != null) {
        inherit domain;
        type = "-";
        item = "memlock";
        value = memlock;
      })
      (lib.optional (nice != null) {
        inherit domain;
        type = "-";
        item = "nice";
        value = toString nice;
      })
    ];

  # ============================================================================
  # Auto-Discovery Helpers
  # ============================================================================

  # Auto-discover NixOS modules in a directory
  # Finds: *.nix files (except default.nix) and subdirs with default.nix
  #
  # Usage in default.nix:
  #   { lib, ... }: { imports = lib.sinnix.mkAutoImports ./.; }
  #
  # Or with exclusions:
  #   { lib, ... }: { imports = lib.sinnix.mkAutoImports ./. [ "deprecated.nix" ]; }
  mkAutoImports =
    dir: exclude:
    let
      excludeSet = lib.listToAttrs (
        map (n: {
          name = n;
          value = true;
        }) exclude
      );
      entries = builtins.readDir dir;
      isModule =
        name: type:
        !excludeSet ? ${name}
        && (
          (type == "regular" && name != "default.nix" && lib.hasSuffix ".nix" name)
          || (type == "directory" && builtins.pathExists (dir + "/${name}/default.nix"))
        );
      moduleNames = lib.filterAttrs isModule entries;
    in
    map (name: dir + "/${name}") (builtins.attrNames moduleNames);

in
{
  inherit
    mkFeatureModule
    mkServiceModule
    mkDotsFileFor
    mkPAMLimits
    ;
  inherit mkAutoImports;
}
