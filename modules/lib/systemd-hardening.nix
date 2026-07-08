{ lib }:
{
  mkRestartPolicy =
    {
      strategy ? "on-failure", # "always" | "on-failure" | "on-abnormal"
      delaySec ? 10,
      maxRetries ? null,
    }:
    {
      Restart = lib.mkDefault strategy;
      RestartSec = lib.mkDefault delaySec;
    }
    // lib.optionalAttrs (maxRetries != null) {
      StartLimitBurst = lib.mkDefault maxRetries;
      StartLimitIntervalSec = lib.mkDefault 300;
    };

  mkRuntimeServiceConfig =
    {
      runtimeInventory,
      unit ? null,
      resourceClass ? null,
      overrides ? { },
      omit ? [ ],
    }:
    let
      resolvedResourceClass =
        if resourceClass != null then
          resourceClass
        else if unit != null then
          let
            matchingSurfaces = lib.filterAttrs (_: surface: surface.unit == unit) runtimeInventory.surfaces;
            surfaceNames = builtins.attrNames matchingSurfaces;
          in
          if surfaceNames == [ ] then
            throw "unknown Sinnix runtime surface unit: ${unit}"
          else
            matchingSurfaces.${builtins.head surfaceNames}.resourceClass
        else
          "system";
      serviceConfig =
        if builtins.hasAttr resolvedResourceClass runtimeInventory.classes then
          runtimeInventory.classes.${resolvedResourceClass}.serviceConfig
        else
          throw "unknown Sinnix runtime resource class: ${resolvedResourceClass}";
      defaults = lib.mapAttrs (_: lib.mkDefault) serviceConfig;
    in
    lib.removeAttrs (defaults // overrides) omit;

  mkGraphicalUserService =
    {
      description,
      execStart,
      target ? "graphical-session.target",
      serviceType ? "simple",
      restart ? "on-failure",
      restartSec ? 1,
      unitExtra ? { },
      serviceExtra ? { },
      installWantedBy ? null,
    }:
    let
      wantedBy = if installWantedBy == null then [ target ] else installWantedBy;
      mergedAfter = (unitExtra.After or [ ]) ++ [ target ];
      mergedPartOf = (unitExtra.PartOf or [ ]) ++ [ target ];
      baseUnit = {
        Description = description;
        After = lib.unique mergedAfter;
        PartOf = lib.unique mergedPartOf;
      };
    in
    {
      Unit =
        baseUnit
        // (lib.removeAttrs unitExtra [
          "After"
          "PartOf"
        ]);
      Service = {
        Type = serviceType;
        ExecStart = execStart;
        Restart = restart;
        RestartSec = restartSec;
      }
      // serviceExtra;
      Install.WantedBy = wantedBy;
    };
}
