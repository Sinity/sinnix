# Desktop notification capture lane
#
# Reference instance of the event-capture-lane template: mkServiceModule
# default-off, user-manager daemon, capture-runtime resource class, writing
# through the shared sinnix-capture envelope library (pkgs/sinnix-capture).
# New lanes should copy this file's shape rather than re-derive it.
#
# The daemon is `scripts/sinnix-capture-notifications-listener`: it runs
# `busctl --user monitor --json=short org.freedesktop.Notifications` (no
# dbus-python/dbus-next dependency) and forwards each Notify() call --
# app_name, summary, body, urgency, actions, timestamp -- to
# `sinnix-capture write --lane notifications`.
{
  mkServiceModule,
  config,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  captureCli = scriptPkgs.sinnix-capture;
  listener = scriptPkgs.sinnix-capture-notifications-listener;
  lane = "notifications";
  laneDir = "${config.sinnix.paths.capturesRoot}/${lane}";
in
mkServiceModule {
  name = "capture-notifications";
  description = "Desktop notification capture: org.freedesktop.Notifications D-Bus monitor -> sinnix-capture";
  surface = {
    unit = "sinnix-capture-notifications.service";
    manager = "user";
    # No explicit `kind`: this owns a real .service unit, so it defaults to
    # "service". `kind = "capture"` is for surfaces with no backing unit;
    # setting it here would silently drop the unit from runtime.nix's
    # OnFailure health-transition wiring (which filters kind == "service").
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = lane;
        path = laneDir;
        eventDriven = true;
        # Event-driven with no numeric cadence, so staleAfterSeconds is the
        # sentinel's only signal (see modules/runtime.nix). Notifications are
        # legitimately bursty and can go silent for many hours (screen off,
        # DND, a quiet afternoon), so anything tighter than a daily
        # "did anything write today" budget false-positives routinely.
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { pkgs, ... }:
    {
      # laneDir lives under /realm, a persistent volume outside impermanence's
      # reach, so no sinnix.persistence entry is needed -- tmpfiles alone
      # provisions capture lanes.
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${userName} users -"
      ];

      home-manager.users.${userName} = {
        systemd.user.services.sinnix-capture-notifications = {
          Unit = {
            Description = "Forward desktop notifications (org.freedesktop.Notifications) to sinnix-capture";
            After = [ "default.target" ];
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-notifications.service";
            overrides = {
              Type = "simple";
              ExecStart = "${listener}/bin/sinnix-capture-notifications-listener --capture-bin ${captureCli}/bin/sinnix-capture --capture-root ${config.sinnix.paths.capturesRoot} --lane ${lane}";
              Restart = "on-failure";
              RestartSec = "5s";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [ laneDir ];
            };
          };
          Install.WantedBy = [ "default.target" ];
        };
      };
    };
} args
