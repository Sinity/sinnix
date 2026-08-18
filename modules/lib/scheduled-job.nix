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
#   timer                 { onCalendar | intervalSec | onUnitActiveSec,
#                           onBootSec, onStartupSec, persistent,
#                           randomizedDelaySec, accuracySec, description }
#                         omit for a service with no timer
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
  timerConfig = lib.optionalAttrs (j ? timer) (
    lib.filterAttrs (_: v: v != null) {
      OnCalendar = j.timer.onCalendar or null;
      # intervalSec computes from seconds; onUnitActiveSec passes a raw
      # systemd duration through untouched ("30min").
      OnUnitActiveSec =
        if j.timer ? intervalSec then "${toString j.timer.intervalSec}s" else j.timer.onUnitActiveSec or null;
      OnBootSec = j.timer.onBootSec or null;
      OnStartupSec = j.timer.onStartupSec or null;
      Persistent = if j.timer.persistent or false then true else null;
      RandomizedDelaySec = j.timer.randomizedDelaySec or null;
      AccuracySec = j.timer.accuracySec or null;
    }
  );
  overrides =
    assert lib.assertMsg ((j ? execStart) != (j ? script))
      "mkScheduledJob ${unitName}: exactly one of execStart or script";
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
  surfaceCoversFailure =
    surface != null
    && (surface.unit or null) == "${unitName}.service"
    && (surface.manager or "system") == manager
    && (surface.observe.enable or false);
  serviceBody = {
    description = j.description or description;
    serviceConfig =
      if manager == "system" then
        systemdLib.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "${unitName}.service";
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
    timers.${unitName} = timerBody;
  };
in
if manager == "user" then { systemd.user = units; } else { systemd = units; }
