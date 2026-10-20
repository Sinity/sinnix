# Typed producer declarations render into the existing runtime inventory.
# Public enable and device options stay with the owning service module.
{ config, lib, ... }:
let
  inherit (lib) mkOption types;
  nullable =
    type: default:
    mkOption {
      type = types.nullOr type;
      inherit default;
    };
  value = type: default: mkOption { inherit type default; };
  outputType = import ./lib/capture-output-type.nix { inherit lib; };
  timerType = types.submodule {
    options = {
      intervalSec = mkOption { type = types.ints.positive; };
      onBootSec = nullable types.str null;
      onStartupSec = nullable types.str null;
      accuracySec = nullable types.str null;
      persistent = value types.bool false;
      description = nullable types.str null;
    };
  };
  producerType = types.submodule {
    options = {
      description = mkOption { type = types.str; };
      execStart = mkOption { type = types.str; };
      directories = value (types.listOf types.str) [ ];
      outputs = mkOption { type = types.listOf outputType; };
      operatorRestart = value types.bool true;
      environment = value (types.listOf types.str) [ ];
      poll = nullable (types.submodule {
        options = {
          timer = mkOption { type = timerType; };
          after = value (types.listOf types.str) [ ];
        };
      }) null;
      stream = nullable (types.submodule {
        options = {
          target = value types.str "graphical-session.target";
          partOf = value types.bool true;
          wantedBy = nullable (types.listOf types.str) null;
          startLimit = nullable (types.submodule {
            options = {
              intervalSec = mkOption { type = types.either types.int types.str; };
              burst = mkOption { type = types.ints.positive; };
            };
          }) null;
        };
      }) null;
    };
  };
  render =
    name: producer:
    let
      unitName = "sinnix-${name}";
      unit = "${unitName}.service";
      surface = {
        inherit unit;
        manager = "user";
        resourceClass = "capture";
        inherit (producer) operatorRestart;
        notifyOnFailure = true;
        captures = producer.outputs;
      };
      overrides = {
        ExecStart = producer.execStart;
        NoNewPrivileges = true;
      }
      // lib.optionalAttrs (producer.environment != [ ]) { Environment = producer.environment; }
      // {
        UMask = "0077";
      };
    in
    {
      inherit surface;
      rules = map (path: "d ${path} 0700 ${config.sinnix.user.name} users -") producer.directories;
      scheduled =
        if producer.poll == null then
          { }
        else
          (lib.sinnix.mkScheduledJob
            {
              inherit config unitName surface;
              description = producer.description;
            }
            {
              manager = "user";
              inherit (producer) execStart;
              resourceClass = "capture";
              serviceConfig = builtins.removeAttrs overrides [ "ExecStart" ];
              timer = lib.filterAttrs (_: v: v != null) producer.poll.timer;
              unit.after = producer.poll.after;
            }
          ).systemd;
      session =
        if producer.stream == null then
          { }
        else
          {
            ${config.sinnix.user.name}.systemd.user.services.${unitName} = {
              Unit = {
                Description = producer.description;
                After = [ producer.stream.target ];
              }
              // lib.optionalAttrs producer.stream.partOf { PartOf = [ producer.stream.target ]; }
              // lib.optionalAttrs (producer.stream.startLimit != null) {
                StartLimitIntervalSec = producer.stream.startLimit.intervalSec;
                StartLimitBurst = producer.stream.startLimit.burst;
              };
              Service = lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                manager = "user";
                inherit unit;
                overrides = overrides // {
                  Type = "simple";
                  Restart = "on-failure";
                  RestartSec = "5s";
                };
              };
              Install.WantedBy =
                if producer.stream.wantedBy != null then producer.stream.wantedBy else [ producer.stream.target ];
            };
          };
    };
  rendered = lib.mapAttrs render config.sinnix.capture.producers;

in
{
  options.sinnix.capture.producers = mkOption {
    type = types.attrsOf producerType;
    default = { };
    description = "Enabled unit-owned capture producers; runtime inventory is the generated observation contract.";
  };
  config = {
    assertions = lib.mapAttrsToList (name: producer: {
      assertion = (producer.poll != null) != (producer.stream != null);
      message = "capture producer ${name}: declare exactly one of poll or stream";
    }) config.sinnix.capture.producers;
    sinnix.runtime.units = lib.mapAttrs (_: result: result.surface) rendered;
    systemd = lib.mkMerge (
      [
        {
          tmpfiles.rules = lib.concatMap (result: result.rules) (builtins.attrValues rendered);
        }
      ]
      ++ map (result: result.scheduled) (builtins.attrValues rendered)
    );
    home-manager.users = lib.mkMerge (map (result: result.session) (builtins.attrValues rendered));
  };
}
