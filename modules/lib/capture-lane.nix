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
# expects (poll mode also returns `job`, so mkServiceModule renders its
# unit+timer itself) -- call it as `mkServiceModule (mkCaptureLane { ... })
# args`.
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
  privateTmp ? false,
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
  # After= for the poll-mode oneshot service itself, not the timer (most
  # pollers need nothing here since the timer alone gates when they run;
  # capture-kitty-scrollback needs graphical-session.target because its
  # writer talks to a running kitty).
  pollAfter ? [ ],

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
  # Per-lane unit descriptions, since existing lanes phrase the service's
  # own Unit.Description (what the daemon/oneshot does) and a poll lane's
  # timer Description (why it fires) more specifically than the top-level
  # `description` mkServiceModule shows in `sinnix services list`.
  unitDescription ? description,
  timerDescription ? "Periodic trigger for ${description}",
}:
let
  unitName = "sinnix-${name}";
  unit = "${unitName}.service";

  resolvedWritablePaths = if writablePaths != null then writablePaths else [ laneDir ];
  resolvedTmpfilesRules =
    if tmpfilesRules != null then tmpfilesRules else [ "d ${laneDir} 0755 ${username} users -" ];

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
  }
  // extraSurface;

  # The user manager exports TMPDIR into every unit it starts, and that path
  # is read-only inside ProtectSystem=strict, so every mktemp in the lane
  # fails and the lane silently captures nothing. A lane with PrivateTmp has
  # a writable /tmp of its own; point TMPDIR there unless the lane already
  # said where its tmp lives.
  lanePrivateTmpEnv = lib.optional (
    privateTmp && !(lib.any (e: lib.hasPrefix "TMPDIR=" e) environment)
  ) "TMPDIR=/tmp";
  laneEnvironment = environment ++ lanePrivateTmpEnv;

  baseOverrides = {
    ExecStart = execStart;
    NoNewPrivileges = true;
    ProtectSystem = "strict";
    ProtectHome = "read-only";
    ReadWritePaths = resolvedWritablePaths;
  }
  // lib.optionalAttrs (laneEnvironment != [ ]) { Environment = laneEnvironment; }
  // lib.optionalAttrs (runtimeDirectory != null) { RuntimeDirectory = runtimeDirectory; }
  // lib.optionalAttrs (runtimeDirectoryPreserve != null) {
    RuntimeDirectoryPreserve = runtimeDirectoryPreserve;
  }
  // lib.optionalAttrs (umask != null) { UMask = umask; }
  // lib.optionalAttrs privateTmp { PrivateTmp = true; };

  streamOverrides =
    baseOverrides
    // {
      Type = "simple";
      Restart = restart.strategy;
      RestartSec = restart.delaySec;
    }
    // serviceOverrides;

  # poll mode hands its unit+timer generation to mkServiceModule's `job`
  # mechanism (see modules/lib/features.nix's mkJobConfig) instead of
  # hand-writing home-manager systemd.user.{services,timers} -- this factory
  # supplies only what's capture-specific (ExecStart, hardening, tmpfiles,
  # captures[]/surface); job owns the OnFailure wiring, resource-class
  # resolution, and unit shape. That lands the poll lane at NixOS-level
  # `systemd.user.*` (/etc/systemd/user) rather than home-manager's per-user
  # tree; modules/runtime.nix's failure-notify drop-in is keyed on
  # `surface.unit`/`manager`/`observe.enable`, not on which of those two
  # namespaces declared the unit, so observability is unaffected.
  #
  jobServiceConfig = builtins.removeAttrs baseOverrides [ "ExecStart" ] // serviceOverrides;

  # Every poll timer routes through job: the factory expresses both the
  # computed (intervalSec) and raw (onUnitActiveSec) cadences and both the
  # boot-relative (onBootSec) and session-relative (onStartupSec) anchors,
  # so no lane needs a hand-written timer. onBootSec defaults to "2min"
  # only when the lane gave no anchor of its own.
  pollJob = lib.optionalAttrs (mode == "poll") (
    {
      inherit execStart manager resourceClass;
      description = unitDescription;
      serviceConfig = jobServiceConfig;
    }
    // lib.optionalAttrs (pollAfter != [ ]) {
      unit = {
        after = pollAfter;
      };
    }
    // {
      timer = {
        accuracySec = timer.accuracySec or null;
        persistent = timer.persistent or false;
        description = timerDescription;
      }
      // lib.optionalAttrs (timer ? intervalSec) { inherit (timer) intervalSec; }
      // lib.optionalAttrs (timer ? onUnitActiveSec) { inherit (timer) onUnitActiveSec; }
      // lib.optionalAttrs (timer ? onStartupSec) { inherit (timer) onStartupSec; }
      // lib.optionalAttrs (!(timer ? onStartupSec)) { onBootSec = timer.onBootSec or "2min"; };
    }
  );

  configFn =
    moduleArgs:
    let
      inherit (moduleArgs) config;
      # The extended lib (lib.sinnix.*) exists only on the module args; the
      # file-level lib this factory was imported with is plain nixpkgs lib.
      inherit (moduleArgs) lib;
    in
    lib.mkMerge [
      { systemd.tmpfiles.rules = resolvedTmpfilesRules; }
      (
        if mode == "poll" then
          { }
        else
          {
            home-manager.users.${username} = {
              systemd.user.services.${unitName} = {
                Unit = {
                  Description = unitDescription;
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
  inherit
    name
    description
    extraOptions
    surface
    configFn
    ;
}
// lib.optionalAttrs (mode == "poll") { job = pollJob; }
