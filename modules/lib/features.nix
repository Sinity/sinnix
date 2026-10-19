{ lib }:
let
  mkScheduledJob = import ./scheduled-job.nix { inherit lib; };
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
  # (modules/dotfiles-sweep.nix, etc.) to centralize cross-cutting concerns:
  #   meta.dotfiles.configFile = { "rel/in/xdg" = "rel/in/dots"; ... };
  #   meta.dotfiles.dataFile = { ... };
  # Entries may be strings (simple recursive symlink) or attrsets with
  # source/recursive/force/onChange/executable keys (full HM file declaration).
  mkMetaOption =
    metaValue:
    lib.mkOption {
      type = lib.types.attrsOf lib.types.unspecified;
      default = metaValue;
      description = "Static capability metadata consumed by sweep modules.";
      internal = true;
    };

  # Repo-relative doc that deliberately documents this capability, consumed
  # by modules/lib/capability-index.nix in place of (falling back to) its
  # filename convention (docs/<name>.md). Left null where no doc genuinely
  # exists for the capability -- the index's own filename-convention
  # fallback still applies in that case.
  mkDocsOption =
    docsValue:
    lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = docsValue;
      description = "Repo-relative doc that documents this capability, or null.";
      internal = true;
    };

  # Both user-facing features and fixed services are capabilities.  Keep the
  # common option ownership and enable semantics here so the two public
  # factories cannot drift in their treatment of metadata or nested options.
  mkCapabilityModule =
    {
      capabilityPath,
      description,
      extraOptions ? { },
      generatedOptions ? { },
      meta ? { },
      docs ? null,
      enableDefault,
      configFn,
    }:
    args@{ config, ... }:
    let
      reservedOptionNames = [
        "enable"
        "meta"
        "docs"
      ];
      conflictingOptions = lib.filter (name: extraOptions ? ${name}) reservedOptionNames;
      capabilityName = builtins.concatStringsSep "." capabilityPath;
      optionsForPath =
        if conflictingOptions != [ ] then
          throw "${capabilityName}: extraOptions must not define generated option(s): ${builtins.concatStringsSep ", " conflictingOptions}"
        else
          lib.recursiveUpdate extraOptions generatedOptions
          // {
            enable = (lib.mkEnableOption description) // {
              default = enableDefault config;
            };
            meta = mkMetaOption meta;
            docs = mkDocsOption docs;
          };
      cfg = lib.getAttrFromPath capabilityPath config;
      user = config.sinnix.user.name;
    in
    {
      options = lib.setAttrByPath capabilityPath optionsForPath;
      config = lib.mkIf cfg.enable (configFn (args // { inherit cfg user; }));
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
      docs ? null,
      # CLI, development, and system features are part of every host. Desktop
      # features follow the machine role unless a host declares an exception.
      defaultOnDesktop ? builtins.head path == "desktop",
      configFn,
    }:
    mkCapabilityModule {
      capabilityPath = [
        "sinnix"
        "features"
      ]
      ++ path;
      generatedOptions = mkSubFeatureOptions subFeatures;
      enableDefault = config: !defaultOnDesktop || config.sinnix.machine.isDesktop;
      inherit
        description
        extraOptions
        meta
        docs
        configFn
        ;
    };

  # Service module factory - like mkFeatureModule but for sinnix.services.*
  mkServiceModule =
    {
      name,
      description,
      extraOptions ? { },
      # Attrset, or a function of the module args (config, cfg, pkgs, ...) —
      # the function form exists so a surface can reference config-derived
      # paths without being pushed down into configFn.
      surface ? null,
      meta ? { },
      docs ? null,
      defaultOnDesktop ? false,
      # Declarative scheduled-oneshot job: sugar over
      # lib.sinnix.mkScheduledJob (modules/lib/scheduled-job.nix, where the
      # full spec-key reference lives). Attrset or function of the module
      # args; multi-job modules call mkScheduledJob directly in configFn
      # instead. One extra key over the direct form:
      #   unitName   override of the generated unit base name, for units
      #              that predate the sinnix- prefix; default sinnix-<name>
      # NOTE for the function form: the module system injects _module.args
      # entries (pkgs among them) only for formals the module FILE names, so
      # a job/surface function using pkgs requires the file's own argument
      # pattern to declare pkgs even if nothing else there uses it.
      job ? null,
      configFn ? (_: { }),
    }:
    mkCapabilityModule {
      capabilityPath = [
        "sinnix"
        "services"
        name
      ];
      enableDefault = config: defaultOnDesktop && config.sinnix.machine.isDesktop;
      inherit
        description
        extraOptions
        meta
        docs
        ;
      configFn =
        moduleArgs:
        let
          inherit (moduleArgs) config;
          resolve = v: if builtins.isFunction v then v moduleArgs else v;
          surfaceValue = resolve surface;
          jobValue = resolve job;
          mkJobConfig =
            j:
            mkScheduledJob {
              inherit config description;
              unitName = j.unitName or "sinnix-${name}";
              surface = surfaceValue;
            } (builtins.removeAttrs j [ "unitName" ]);
        in
        lib.mkMerge [
          (lib.optionalAttrs (surfaceValue != null) {
            sinnix.runtime.surfaces.${name} = surfaceValue;
          })
          (lib.optionalAttrs (jobValue != null) (mkJobConfig jobValue))
          (configFn moduleArgs)
        ];
    };

  # AI service specialization. It owns only the repeated surface metadata and
  # persistence declaration and shared container-runtime requirement. Launch
  # commands, users, dependencies, and protocol-specific settings remain in
  # each service module.
  mkAiService =
    {
      name,
      description,
      unit,
      activation ? { },
      resourceClass ? "ordinary",
      stateDirectories ? [ ],
      backendKind ? "native",
      requiresCuda ? false,
      browserRequests ? "loopback",
      extraOptions ? { },
      meta ? { },
      docs ? null,
      configFn,
    }:
    mkServiceModule {
      inherit
        name
        description
        extraOptions
        meta
        docs
        ;
      surface = {
        inherit unit resourceClass activation;
        ai = {
          inherit backendKind requiresCuda browserRequests;
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };
      configFn =
        args:
        lib.mkMerge [
          (lib.optionalAttrs (backendKind == "container") {
            sinnix.ml.containerRuntime.enable = true;
          })
          (lib.optionalAttrs (stateDirectories != [ ]) {
            sinnix.persistence.system.directories = stateDirectories;
          })
          (configFn args)
        ];
    };

  # Pre-curried version for extraSpecialArgs - eliminates boilerplate in modules
  # Usage in home-manager.nix extraSpecialArgs:
  #   mkDotsFileFor = helpers.mkDotsFileFor config.sinnix;
  # Then in HM modules:
  #   { config, mkDotsFileFor, ... }: let mkDotsFile = mkDotsFileFor config; in { ... }
  mkDotsFileFor =
    sinnix: hmConfig: rel:
    hmConfig.lib.file.mkOutOfStoreSymlink (sinnix.paths.dotsRoot + rel);

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
    mkAiService
    mkDotsFileFor
    ;
  inherit mkAutoImports;
}
