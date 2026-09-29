# The one renderer for scheduled-oneshot systemd jobs (service + optional
# timer), in either manager. mkServiceModule's `job` argument is sugar over
# this; feature modules, multi-job service modules, and infrastructure
# modules (runtime.nix, backup.nix) call it directly inside their config —
# there is no second idiom for a oneshot-on-a-timer.
#
# Usage (direct form):
#   lib.sinnix.mkScheduledJob {
#     inherit config;              # module config (runtime inventory lookup)
#     unitName = "sinnix-foo";     # unit base name (service + timer share it)
#     description = "...";         # service Description= default
#     surface = surfaceValue;      # optional: the job's own registered surface,
#                                  # so failure-notify is not attached twice
#     job = { execStart = "..."; timer = { ... }; ... };
#   }
# returns { systemd = { services.<name> = ...; timers.<name> = ...; }; } or
# the systemd.user twin, ready to merge into a module's config.
#
# Job spec keys (all optional unless noted):
#   execStart             full ExecStart string (this or script, exactly one)
#   script                inline shell body (NixOS `script =` semantics);
#                         for jobs whose body is a generated script rather
#                         than a packaged binary
#   timer                 { onCalendar | intervalSec (seconds, rendered as a
#                           calendar step, so it must divide its minute,
#                           hour or day evenly),
#                           onBootSec, onStartupSec, persistent,
#                           randomizedDelaySec, accuracySec, description,
#                           enable ? true }
#                         omit for a service with no timer at all. `enable`
#                         is for the different case of a STATICALLY known
#                         timer spec whose activation is gated by a runtime
#                         option of the SAME module (e.g. a job's own
#                         `job = { cfg, ... }: { timer = { ...; enable =
#                         cfg.timer.enable; }; }` function form): omitting
#                         the `timer` key outright based on forcing that
#                         same-module cfg value to decide the KEY'S
#                         PRESENCE creates a genuine self-referential
#                         blackhole in the module system (the generic
#                         config-merge pass must visit this module's own
#                         `.config` shape to resolve the very cfg option
#                         being forced -- confirmed empirically on
#                         sinnix-oracle's job function, 2026-08-18).
#                         `enable` keeps the `timer` key statically present
#                         (safe: no forcing needed for shape) and instead
#                         wraps the rendered timer unit's VALUE in
#                         `lib.mkIf`, the same deferred-marker mechanism
#                         that already makes `cfg.enable` -> `mkIf cfg.enable`
#                         safe everywhere else in this factory.
#   manager ? "system"    "system" | "user"
#   user                  system-manager User= (evidence lives in a user's
#                         own stores)
#   serviceConfig ? { }   extra overrides merged over the generated ones
#   path, environment, description   passed through to the unit
#   resourceClass         user-manager only: apply this class's serviceConfig
#                         via mkRuntimeServiceConfig's direct-class form
#                         (no unit lookup)
#   unit ? { }            extra unit-level attrs merged into the generated
#                         service (after, requires, unitConfig,
#                         restartIfChanged, ...)
{ lib }:
let
  systemdLib = import ./systemd-hardening.nix { inherit lib; };
in
{
  config,
  unitName,
  description,
  surface ? null,
}:
j:
let
  manager = j.manager or "system";
  # Every cadence is wall-clock. A unit-relative OnUnitActiveSec anchors on
  # the service's activation, and a Type=oneshot job that fails to start (a
  # wedged manager queue, an activation mid-switch) leaves the timer with no
  # next elapse: it stops for good and nothing reports it. A calendar step is
  # anchored outside the unit, so no run outcome can end the cadence.
  intervalCalendar =
    seconds:
    assert lib.assertMsg (builtins.isInt seconds && seconds > 0)
      "mkScheduledJob ${unitName}: intervalSec must be a positive integer of seconds, got ${builtins.toJSON seconds}";
    if seconds < 60 && lib.mod 60 seconds == 0 then
      "*:*:0/${toString seconds}"
    else if seconds < 3600 && lib.mod seconds 60 == 0 && lib.mod 60 (seconds / 60) == 0 then
      "*:0/${toString (seconds / 60)}"
    else if seconds <= 86400 && lib.mod seconds 3600 == 0 && lib.mod 24 (seconds / 3600) == 0 then
      "0/${toString (seconds / 3600)}:00:00"
    else
      throw "mkScheduledJob ${unitName}: intervalSec ${toString seconds} does not divide its minute, hour or day evenly; choose a divisor or declare onCalendar";
  timerConfig = lib.optionalAttrs (j ? timer) (
    assert lib.assertMsg (!(j.timer ? onUnitActiveSec))
      "mkScheduledJob ${unitName}: onUnitActiveSec is refused (a unit-relative timer stops after one failed start); declare intervalSec or onCalendar";
    assert lib.assertMsg (
      !(j.timer ? intervalSec && j.timer ? onCalendar)
    ) "mkScheduledJob ${unitName}: declare intervalSec or onCalendar, not both";
    lib.filterAttrs (_: v: v != null) {
      OnCalendar =
        if j.timer ? intervalSec then intervalCalendar j.timer.intervalSec else j.timer.onCalendar or null;
      OnBootSec = j.timer.onBootSec or null;
      OnStartupSec = j.timer.onStartupSec or null;
      Persistent = if j.timer.persistent or false then true else null;
      RandomizedDelaySec = j.timer.randomizedDelaySec or null;
      AccuracySec = j.timer.accuracySec or null;
    }
  );
  overrides =
    assert lib.assertMsg (
      (j ? execStart) != (j ? script)
    ) "mkScheduledJob ${unitName}: exactly one of execStart or script";
    {
      Type = "oneshot";
    }
    // lib.optionalAttrs (j ? execStart) { ExecStart = j.execStart; }
    // lib.optionalAttrs (j ? user) { User = j.user; }
    // (j.serviceConfig or { });
  # Failure reporting is a property of unit registration, not of each module
  # remembering to ask for it: a generated job attaches sinnix's
  # failure-notify template itself, in its own manager. Skipped when this
  # job's own surface already carries it -- modules/runtime.nix attaches the
  # same template to every observed surface, and a unit naming one dependency
  # twice is noise.
  # A job may register its surface on the timer rather than the service (a
  # submission job's policy belongs to the schedule). Only this service's own
  # surface can answer a unit lookup for it.
  surfaceIsThisService =
    surface != null
    && (surface.unit or null) == "${unitName}.service"
    && (surface.manager or "system") == manager;
  surfaceCoversFailure = surfaceIsThisService && (surface.observe.enable or false);
  serviceBody = {
    description = j.description or description;
    serviceConfig =
      if surfaceIsThisService then
        systemdLib.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "${unitName}.service";
          inherit manager;
          inherit overrides;
        }
      else if j ? resourceClass then
        systemdLib.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          inherit (j) resourceClass;
          inherit overrides;
        }
      else
        overrides;
  }
  // lib.optionalAttrs (!surfaceCoversFailure) {
    onFailure = lib.mkDefault [ "sinnix-unit-failure-notify@%n.service" ];
  }
  // lib.optionalAttrs (j ? path) { path = j.path; }
  // lib.optionalAttrs (j ? environment) { environment = j.environment; }
  // lib.optionalAttrs (j ? script) { script = j.script; }
  // (j.unit or { });
  timerBody = {
    wantedBy = [ "timers.target" ];
    inherit timerConfig;
  }
  // lib.optionalAttrs (j ? timer && j.timer ? description) {
    description = j.timer.description;
  };
  units = {
    services.${unitName} = serviceBody;
  }
  // lib.optionalAttrs (j ? timer) {
    # mkIf, not a plain value: this is the ONLY point where `timer.enable`
    # (see the doc comment above) gets forced, and mkIf is a marker the
    # module system's generic config-merge pass defers to leaf-read time
    # rather than needing during shape/key-presence resolution.
    timers.${unitName} = lib.mkIf (j.timer.enable or true) timerBody;
  };
in
if manager == "user" then { systemd.user = units; } else { systemd = units; }
