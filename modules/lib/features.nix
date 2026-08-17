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
  # (modules/dotfiles-sweep.nix, etc.) to centralize cross-cutting concerns:
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
      # Features in modules/features/ are unconditionally part of a sinnix
      # host's default character; hosts express exceptions via
      # `sinnix.features.<path>.enable = false`. defaultOn is an explicit
      # escape hatch, not routine tuning — optional background capabilities
      # belong in the default-off service namespace instead.
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
      # extraOptions must not define its own top-level `enable`: the `//`
      # merge below replaces it wholesale, silently discarding whatever a
      # caller declared there.
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
      # Attrset, or a function of the module args (config, cfg, pkgs, ...) —
      # the function form exists so a surface can reference config-derived
      # paths without being pushed down into configFn.
      surface ? null,
      meta ? { },
      # Declarative scheduled-oneshot job. Attrset or function of the module
      # args. NOTE for the function form: the module system injects
      # _module.args entries (pkgs among them) only for formals the module
      # FILE names, so a job/surface function using pkgs requires the file's
      # own argument pattern to declare pkgs even if nothing else there uses
      # it. Keys:
      #   execStart (required)  full ExecStart string
      #   timer                 { onCalendar | intervalSec, onBootSec,
      #                           persistent, randomizedDelaySec, accuracySec }
      #                         omit for a service with no timer
      #   manager ? "system"    "system" | "user"
      #   user                  system-manager User= (evidence lives in a
      #                         user's own stores)
      #   serviceConfig ? { }   extra overrides merged over the generated ones
      #   path, environment, description   passed through to the unit
      # The unit is always sinnix-<name>.service; system-manager jobs get
      # their resource class via mkRuntimeServiceConfig (register the
      # surface), user-manager jobs write plain serviceConfig, matching
      # existing per-manager practice.
      job ? null,
      configFn ? (_: { }),
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
      moduleArgs = args // {
        inherit cfg;
      };
      resolve = v: if builtins.isFunction v then v moduleArgs else v;
      surfaceValue = resolve surface;
      jobValue = resolve job;
      unitName = "sinnix-${name}";
      mkJobConfig =
        j:
        let
          manager = j.manager or "system";
          timerConfig = lib.optionalAttrs (j ? timer) (
            lib.filterAttrs (_: v: v != null) {
              OnCalendar = j.timer.onCalendar or null;
              OnUnitActiveSec = if j.timer ? intervalSec then "${toString j.timer.intervalSec}s" else null;
              OnBootSec = j.timer.onBootSec or null;
              Persistent = if j.timer.persistent or false then true else null;
              RandomizedDelaySec = j.timer.randomizedDelaySec or null;
              AccuracySec = j.timer.accuracySec or null;
            }
          );
          overrides = {
            Type = "oneshot";
            ExecStart = j.execStart;
          }
          // lib.optionalAttrs (j ? user) { User = j.user; }
          // (j.serviceConfig or { });
          serviceBody = {
            description = j.description or description;
            serviceConfig =
              if manager == "system" then
                lib.sinnix.mkRuntimeServiceConfig {
                  runtimeInventory = config.sinnix.runtime.inventory;
                  unit = "${unitName}.service";
                  inherit overrides;
                }
              else
                overrides;
          }
          // lib.optionalAttrs (j ? path) { path = j.path; }
          // lib.optionalAttrs (j ? environment) { environment = j.environment; };
          timerBody = {
            wantedBy = [ "timers.target" ];
            inherit timerConfig;
          };
          units =
            {
              services.${unitName} = serviceBody;
            }
            // lib.optionalAttrs (j ? timer) {
              timers.${unitName} = timerBody;
            };
        in
        if manager == "user" then { systemd.user = units; } else { systemd = units; };
    in
    {
      options = lib.setAttrByPath servicePath optionsForPath;
      config = lib.mkIf cfg.enable (
        lib.mkMerge [
          (lib.optionalAttrs (surfaceValue != null) {
            sinnix.runtime.surfaces.${name} = surfaceValue;
          })
          (lib.optionalAttrs (jobValue != null) (mkJobConfig jobValue))
          (configFn moduleArgs)
        ]
      );
    };

  # AI service specialization. It owns only the repeated surface metadata and
  # persistence declaration. Launch commands, users, dependencies, and
  # protocol-specific settings remain in each service module.
  mkAiService =
    {
      name,
      description,
      unit,
      endpoint ? null,
      activation ? { },
      resourceClass ? "interactive-agent",
      stateDirectories ? [ ],
      backendKind ? "native",
      requiresCuda ? false,
      extraOptions ? { },
      meta ? { },
      configFn,
    }:
    mkServiceModule {
      inherit name description extraOptions;
      meta = meta // {
        ai = {
          inherit backendKind requiresCuda;
        };
      };
      surface = {
        inherit unit resourceClass;
        activation = {
          mode = "direct";
        }
        // lib.optionalAttrs (endpoint != null) {
          publicEndpoint = endpoint;
        }
        // activation;
        observe = {
          enable = true;
          restartable = true;
        };
      };
      configFn =
        args:
        lib.mkMerge [
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

  # Standard shell env-var name for a secret (matches modules/secrets.nix's
  # own agenix-export derivation): upper-SNAKE_CASE, dots and dashes both
  # collapse to underscores.
  secretEnvName = secretName: lib.toUpper (lib.replaceStrings [ "-" "." ] [ "_" "_" ] secretName);

  # Standard secret-resolution shell fragment: prefer an already-exported env
  # var, else read the agenix runtime path if readable, else fail loudly.
  # Leaves the resolved value exported in `varName` (defaults to the secret's
  # derived env-var name).
  #
  # Usage: mkSecretLookup { secretName = "deepseek-api-key"; varName = "OPENAI_API_KEY"; caller = "hermes-deepseek"; }
  mkSecretLookup =
    {
      # Bare secret name as it appears under secret/<name>.age and
      # /run/agenix/<name> (see modules/secrets.nix auto-discovery).
      secretName,
      # Wrapper/script name used in the error message, e.g. "hermes-deepseek".
      caller,
      # Shell variable the resolved value ends up exported in.
      varName ? secretEnvName secretName,
      # Runtime path override; defaults to the standard agenix path.
      agenixPath ? "/run/agenix/${secretName}",
    }:
    let
      envName = secretEnvName secretName;
      path = lib.escapeShellArg agenixPath;
    in
    ''
      if [ -n "''${${envName}:-}" ]; then
        ${
          # When the caller wants the secret in its own derived env var, the
          # value is already exactly where it belongs -- emitting
          # `FOO="$FOO"` here is a self-assignment shellcheck rejects
          # (SC2269), which fails any writeShellApplication caller.
          if varName == envName then ":" else ''${varName}="''${${envName}}"''
        }
      elif [ -r ${path} ]; then
        ${varName}="$(<${path})"
      else
        echo "${caller}: no ${secretName} available (set ${envName} or ensure ${agenixPath} is readable)" >&2
        exit 1
      fi
      export ${varName}
    '';

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
    mkPAMLimits
    mkSecretLookup
    ;
  inherit mkAutoImports;
}
