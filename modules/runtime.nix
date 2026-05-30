# Runtime inventory registry
#
# One source of truth for Sinnix runtime surfaces, resource classes, systemd
# slices, command wrappers, static slice budgets, and capture inventory.
{
  lib,
  config,
  helpers,
  ...
}:
let
  cfg = config.sinnix;
  inherit (helpers.data) runtimeDefaults;
  resourceClassNames = builtins.attrNames runtimeDefaults.classes;

  surfaces = config.sinnix.runtime.surfaces;
  surfaceRows = lib.mapAttrsToList (name: surface: {
    inherit name;
    inherit (surface)
      kind
      manager
      resourceClass
      unit
      ;
  }) surfaces;
  surfaceUnitKeys = map (surface: "${surface.manager}:${surface.unit}") surfaceRows;
  duplicateSurfaceUnitKeys = lib.unique (
    builtins.filter (
      key: (builtins.length (builtins.filter (candidate: candidate == key) surfaceUnitKeys)) > 1
    ) surfaceUnitKeys
  );
  kindUnitMismatches = builtins.filter (
    surface: surface.kind != "capture" && !(lib.hasSuffix ".${surface.kind}" surface.unit)
  ) surfaceRows;
  commandRows = lib.mapAttrsToList (name: command: {
    inherit name;
    inherit (command) resourceClass;
  }) runtimeDefaults.commandClasses;
  unknownCommandClasses = builtins.filter (
    command: !(builtins.elem command.resourceClass resourceClassNames)
  ) commandRows;

  mountMonitoring = [
    {
      path = cfg.paths.realmRoot;
      warnPct = 80;
      failPct = 90;
    }
    {
      path = cfg.paths.neoOuterRealm;
      warnPct = 80;
      failPct = 90;
    }
  ];

  backupInventory = {
    snapshotDirs = [
      "${cfg.paths.realmRoot}/.btrfs/snapshot"
      "/persist/.btrfs/snapshot"
    ];
    backupTargets = [ ];
    drillLog = "${cfg.paths.capturesRoot}/machine/borg_drill.jsonl";
  };

  runtimeInventory = runtimeDefaults.mkInventory {
    hostname = config.networking.hostName;
    inherit surfaces;
    mounts = mountMonitoring;
    backups = backupInventory;
  };
in
{
  options.sinnix.runtime.surfaces = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule {
        options = {
          unit = lib.mkOption {
            type = lib.types.str;
            description = "systemd unit name owned by this runtime surface.";
          };
          manager = lib.mkOption {
            type = lib.types.enum [
              "system"
              "user"
            ];
            default = "system";
            description = "systemd manager that owns the unit.";
          };
          kind = lib.mkOption {
            type = lib.types.enum [
              "service"
              "socket"
              "timer"
              "target"
              "slice"
              "capture"
            ];
            default = "service";
            description = "Runtime surface kind.";
          };
          resourceClass = lib.mkOption {
            type = lib.types.enum resourceClassNames;
            default = "system";
            description = "Sinnix runtime resource class.";
          };
          observe = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Expose this surface in /etc/sinnix/runtime-inventory.json.";
            };
            restartable = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Whether operators may restart this surface directly.";
            };
          };
          captures = lib.mkOption {
            type = lib.types.listOf (
              lib.types.submodule {
                options = {
                  name = lib.mkOption { type = lib.types.str; };
                  path = lib.mkOption { type = lib.types.str; };
                  cadenceSeconds = lib.mkOption {
                    type = lib.types.nullOr lib.types.int;
                    default = null;
                  };
                  eventDriven = lib.mkOption {
                    type = lib.types.bool;
                    default = false;
                  };
                };
              }
            );
            default = [ ];
            description = "Capture outputs produced by this runtime surface.";
          };
        };
      }
    );
    default = { };
    description = "Enabled runtime units and capture surfaces declared by owning modules.";
  };

  options.sinnix.runtime.inventory = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = runtimeInventory;
    description = "Canonical Sinnix runtime surfaces, resource classes, slices, command policy, and capture inventory.";
  };

  config = {
    assertions = [
      {
        assertion = duplicateSurfaceUnitKeys == [ ];
        message =
          "sinnix.runtime.surfaces must not declare duplicate manager/unit pairs: "
          + lib.concatStringsSep ", " duplicateSurfaceUnitKeys;
      }
      {
        assertion = kindUnitMismatches == [ ];
        message =
          "sinnix.runtime.surfaces unit suffixes must match their kind: "
          + lib.concatMapStringsSep ", " (
            surface: "${surface.name}:${surface.kind}:${surface.unit}"
          ) kindUnitMismatches;
      }
      {
        assertion = unknownCommandClasses == [ ];
        message =
          "sinnix.runtime.inventory.commandClasses use unknown resource classes: "
          + lib.concatMapStringsSep ", " (
            command: "${command.name}:${command.resourceClass}"
          ) unknownCommandClasses;
      }
    ];

    sinnix.runtime.surfaces = runtimeDefaults.baseSurfaces;

    environment.etc."sinnix/runtime-inventory.json" = {
      text = builtins.toJSON config.sinnix.runtime.inventory;
      mode = "0444";
    };
  };
}
