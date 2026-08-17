# mkCaptureLane: the shared shape behind modules/services/capture-*.nix.
#
# Every capture lane is one of two things:
#   - "poll": a oneshot writer triggered by a systemd --user timer
#     (capture-awair, capture-monitor, capture-router, ...).
#   - "stream": a long-running writer tied to a session lifecycle target
#     (capture-notifications, capture-clipboard, capture-a11y, ...).
#
# Both shapes share: a tmpfiles-provisioned lane directory, a
# `sinnix.runtime.surfaces.<name>` entry carrying `captures[]`, and the same
# hardening set (NoNewPrivileges, ProtectSystem=strict, ProtectHome=read-only,
# a narrow ReadWritePaths). mkCaptureLane encodes that shape once; callers
# supply only what actually varies (the writer's ExecStart, cadence/staleness
# budgets, and any lane-specific overrides) and get back the `{ name;
# description; extraOptions; surface; configFn; }` attrset mkServiceModule
# expects -- call it as `mkServiceModule (mkCaptureLane { ... }) args`.
#
# Deliberately NOT covered here (see modules/services/*.nix for why each
# stays hand-rolled): capture-audio (three cooperating units sharing one
# --capture-root), capture-replay (mutually-exclusive with sandboxing --
# gpu-screen-recorder's cap_sys_admin needs the initial namespace),
# capture-netflow (system-manager unit with an ambient-capability
# ExecStartPre root step), terminal-capture (no owning unit at all -- a
# `sinnix.runtime.captures` lane, not a surface).
{ lib }:
{
  name,
  description,
  # Full ExecStart string (already resolved store paths / cfg-derived args --
  # build it the same way job.execStart is built for mkServiceModule).
  execStart,
  # Directory this lane's writer needs. Drives the default tmpfiles rule and
  # the default single-entry captures[] / ReadWritePaths -- override
  # tmpfilesRules / captures / writablePaths for a multi-directory lane
  # (see capture-clipboard's laneDir+blobDir+stateDir, capture-router's four
  # sub-lanes under one routerRoot).
  laneDir ? null,
  username,
  extraOptions ? { },
  manager ? "user",
  resourceClass ? "capture-runtime",
  restartable ? true,
  # "poll" (oneshot + timer) or "stream" (long-running, session-lifecycle).
  mode,

  # --- captures[] (sinnix.runtime.surfaces.<name>.captures) ---
  # captureName defaults to the service `name`'s "capture-" suffix stripped,
  # matching every existing lane's convention (capture-awair -> "environment"
  # is the one exception, so callers with a differently-named lane pass
  # captureName explicitly).
  captureName ? name,
  cadenceSeconds ? null,
  staleAfterSeconds ? null,
  eventDriven ? false,
  requiredPayloadFields ? null,
  livenessProbe ? null,
  # Full override for multi-lane surfaces (capture-router's four sub-lanes).
  # When set, laneDir/cadenceSeconds/staleAfterSeconds/eventDriven/
  # requiredPayloadFields/livenessProbe above are ignored for captures[] --
  # they may still drive the default tmpfiles rule / writablePaths.
  captures ? null,
  extraSurface ? { },

  # --- tmpfiles ---
  # Raw `d <path> <mode> <user> <group> -` rule strings. Defaults to one rule
  # for laneDir at 0755.
  tmpfilesRules ? null,

  # --- hardening / exec ---
  # ReadWritePaths. Defaults to [ laneDir ].
  writablePaths ? null,
  environment ? [ ],
  runtimeDirectory ? null,
  runtimeDirectoryPreserve ? null,
  umask ? null,
  # Merged last over the generated Service overrides -- escape hatch for a
  # lane-specific knob (capture-monitor's XDG_CACHE_HOME, capture-a11y's
  # GI_TYPELIB_PATH) that doesn't warrant its own factory parameter.
  serviceOverrides ? { },

  # --- mode = "poll" ---
  # { intervalSec (required); onBootSec ? "2min"; onStartupSec ?; accuracySec
  #   ? "10s"; persistent ? false; }. onStartupSec and onBootSec are
  #   mutually exclusive (systemd itself allows both, but every existing
  #   lane picks one); set onBootSec = null to use onStartupSec instead.
  timer ? { },

  # --- mode = "stream" ---
  target ? "graphical-session.target",
  partOf ? true,
  extraAfter ? [ ],
  wantedBy ? null, # defaults to [ target ]
  startLimit ? null, # { intervalSec; burst; }
  restart ? {
    strategy = "on-failure";
    delaySec = "5s";
  },

  # Merged in alongside the generated tmpfiles/unit config -- for anything a
  # lane needs beyond the unit itself (capture-a11y's at-spi2-core enable,
  # environment.sessionVariables).
  extraConfig ? (_: { }),
}:
let
  unitName = "sinnix-${name}";
  unit = "${unitName}.service";

  resolvedWritablePaths = if writablePaths != null then writablePaths else [ laneDir ];
  resolvedTmpfilesRules =
    if tmpfilesRules != null then
      tmpfilesRules
    else
      [ "d ${laneDir} 0755 ${username} users -" ];

  defaultCaptures = lib.optional (laneDir != null) (
    {
      name = captureName;
      path = laneDir;
    }
    // lib.optionalAttrs (cadenceSeconds != null) { inherit cadenceSeconds; }
    // lib.optionalAttrs eventDriven { eventDriven = true; }
    // lib.optionalAttrs (staleAfterSeconds != null) { inherit staleAfterSeconds; }
    // lib.optionalAttrs (requiredPayloadFields != null) { inherit requiredPayloadFields; }
    // lib.optionalAttrs (livenessProbe != null) { inherit livenessProbe; }
  );
  resolvedCaptures = if captures != null then captures else defaultCaptures;

  surface = {
    inherit unit manager resourceClass;
    observe = {
      enable = true;
      inherit restartable;
    };
    captures = resolvedCaptures;
  } // extraSurface;

  baseOverrides =
    {
      ExecStart = execStart;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = resolvedWritablePaths;
    }
    // lib.optionalAttrs (environment != [ ]) { Environment = environment; }
    // lib.optionalAttrs (runtimeDirectory != null) { RuntimeDirectory = runtimeDirectory; }
    // lib.optionalAttrs (
      runtimeDirectoryPreserve != null
    ) { RuntimeDirectoryPreserve = runtimeDirectoryPreserve; }
    // lib.optionalAttrs (umask != null) { UMask = umask; };

  pollOverrides = baseOverrides // {
    Type = "oneshot";
  };

  streamOverrides =
    baseOverrides
    // {
      Type = "simple";
      Restart = restart.strategy;
      RestartSec = restart.delaySec;
    }
    // serviceOverrides;

  configFn =
    moduleArgs:
    let
      inherit (moduleArgs) config;
    in
    lib.mkMerge [
      { systemd.tmpfiles.rules = resolvedTmpfilesRules; }
      (
        if mode == "poll" then
          {
            home-manager.users.${username} = {
              systemd.user.services.${unitName} = {
                Unit.Description = description;
                Service = lib.sinnix.mkRuntimeServiceConfig {
                  runtimeInventory = config.sinnix.runtime.inventory;
                  inherit unit;
                  overrides = pollOverrides // serviceOverrides;
                };
              };
              systemd.user.timers.${unitName} = {
                Unit.Description = "Periodic trigger for ${description}";
                Timer =
                  let
                    onStartupSec = timer.onStartupSec or null;
                  in
                  { OnUnitActiveSec = "${toString timer.intervalSec}s"; }
                  // (
                    if onStartupSec != null then
                      { OnStartupSec = onStartupSec; }
                    else
                      { OnBootSec = timer.onBootSec or "2min"; }
                  )
                  // lib.optionalAttrs ((timer.accuracySec or null) != null) {
                    AccuracySec = timer.accuracySec;
                  }
                  // lib.optionalAttrs (timer.persistent or false) { Persistent = true; };
                Install.WantedBy = [ "timers.target" ];
              };
            };
          }
        else
          {
            home-manager.users.${username} = {
              systemd.user.services.${unitName} = {
                Unit =
                  {
                    Description = description;
                    After = [ target ] ++ extraAfter;
                  }
                  // lib.optionalAttrs partOf { PartOf = [ target ]; }
                  // lib.optionalAttrs (startLimit != null) {
                    StartLimitIntervalSec = startLimit.intervalSec;
                    StartLimitBurst = startLimit.burst;
                  };
                Service = lib.sinnix.mkRuntimeServiceConfig {
                  runtimeInventory = config.sinnix.runtime.inventory;
                  inherit unit;
                  overrides = streamOverrides;
                };
                Install.WantedBy = if wantedBy != null then wantedBy else [ target ];
              };
            };
          }
      )
      (extraConfig moduleArgs)
    ];
in
{
  inherit name description extraOptions surface configFn;
}
