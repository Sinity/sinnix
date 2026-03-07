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

  mkFeatureModule =
    {
      path,
      description,
      enableDefault ? false,
      extraOptions ? { },
      # NEW: Declarative sub-features
      # subFeatures = { vscode = { description = "VSCode"; default = true; }; ... }
      subFeatures ? { },
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
      optionsForPath =
        lib.recursiveUpdate extraOptions subFeatureOpts
        // {
          enable = (lib.mkEnableOption description) // {
            default = enableDefault;
          };
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
      health ? null,
      configFn,
    }:
    args@{ config, lib, ... }:
    let
      servicePath = [
        "sinnix"
        "services"
        name
      ];
      healthOption = lib.optionalAttrs (health != null) {
        health = lib.mkOption {
          type = lib.types.nullOr (
            lib.types.submodule {
              options = {
                unit = lib.mkOption {
                  type = lib.types.str;
                  description = "systemd unit name for health monitoring.";
                };
                type = lib.mkOption {
                  type = lib.types.enum [
                    "service"
                    "timer"
                    "user"
                  ];
                  description = "How sentinel should query the unit.";
                };
                restartable = lib.mkOption {
                  type = lib.types.bool;
                  description = "Whether sentinel may auto-restart this unit.";
                };
              };
            }
          );
          default = health;
          description = "Service health metadata consumed by introspection/sentinel.";
        };
      };
      optionsForPath =
        extraOptions
        // healthOption
        // {
          enable = lib.mkEnableOption description;
        };
      cfg = lib.getAttrFromPath servicePath config;
    in
    {
      options = lib.setAttrByPath servicePath optionsForPath;
      config = lib.mkIf cfg.enable (configFn (args // { inherit cfg; }));
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

  # ============================================================================
  # Bundle Factory
  # ============================================================================

  # Create a bundle module that enables features by path pattern
  #
  # Usage:
  #   mkBundleModule {
  #     name = "desktop";
  #     description = "Standard Desktop Environment";
  #     featureDomain = "desktop";  # enables all sinnix.features.desktop.*
  #     extraEnables = {            # additional features outside domain
  #       "features.system.nix-ld" = true;
  #     };
  #   }
  mkBundleModule =
    {
      name,
      description,
      # Primary domain to auto-enable (e.g., "desktop" → features.desktop.*)
      featureDomain,
      # Extra features to enable (path strings relative to sinnix)
      extraEnables ? { },
      # Features to exclude from auto-enable
      excludeFeatures ? [ ],
    }:
    { config, lib, ... }:
    let
      bundlePath = [
        "sinnix"
        "bundles"
        name
      ];
      cfg = lib.getAttrFromPath bundlePath config;

      # Get all features in the domain
      domainFeatures = config.sinnix.features.${featureDomain} or { };

      # Filter to only features with .enable option, excluding specified ones
      excludeSet = lib.listToAttrs (
        map (n: {
          name = n;
          value = true;
        }) excludeFeatures
      );
      enableableFeatures = lib.filterAttrs (n: v: v ? enable && !excludeSet ? ${n}) domainFeatures;

      # Generate enable statements for domain features
      domainEnables = lib.mapAttrs (_: _: { enable = true; }) enableableFeatures;

      # Parse extra enables (path string → nested attrs)
      parseExtraEnables = lib.mapAttrs' (path: value: {
        name = builtins.head (lib.splitString "." path);
        value =
          let
            parts = lib.splitString "." path;
            rest = builtins.tail parts;
          in
          if rest == [ ] then { enable = value; } else lib.setAttrByPath rest { enable = value; };
      }) extraEnables;
    in
    {
      options = lib.setAttrByPath bundlePath {
        enable = lib.mkEnableOption description;
      };

      config = lib.mkIf cfg.enable {
        sinnix = lib.mkMerge [
          { features.${featureDomain} = domainEnables; }
          parseExtraEnables
        ];
      };
    };

in
{
  inherit
    mkFeatureModule
    mkServiceModule
    mkDotsFileFor
    mkPAMLimits
    ;
  inherit mkAutoImports mkBundleModule;
}
