# Desktop notification capture lane
#
# Reference instance of the event-capture-lane template: mkServiceModule
# desktop-default, user-manager daemon, capture resource class, writing
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
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  captureCli = scriptPkgs.sinnix-capture;
  listener = scriptPkgs.sinnix-capture-notifications-listener;
  lane = "notifications";
  laneDir = config.sinnix.paths.capturePaths.${lane};
in
mkServiceModule {
  name = "capture-notifications";
  defaultOnDesktop = true;
  description = "Desktop notification capture: org.freedesktop.Notifications D-Bus monitor -> sinnix-capture";
  # laneDir lives under /realm, a persistent volume outside impermanence's
  # reach, so no sinnix.persistence entry is needed -- tmpfiles alone
  # provisions capture lanes.
  configFn = _: {
    sinnix.capture.producers.capture-notifications = {
      directories = [ laneDir ];
      outputs = [
        {
          name = lane;
          path = laneDir;
          eventDriven = true;
          # Event-driven with no numeric cadence, so staleAfterSeconds is the
          # health sweep's only signal (see modules/runtime.nix). Notifications are
          # legitimately bursty and can go silent for many hours (screen off, DND,
          # a quiet afternoon), so anything tighter than a daily "did anything write
          # today" budget false-positives routinely.
          staleAfterSeconds = 86400;
        }
      ];
      stream.target = "default.target";
      stream.partOf = false;
      execStart = "${listener}/bin/sinnix-capture-notifications-listener --capture-bin ${captureCli}/bin/sinnix-capture --capture-root ${config.sinnix.paths.activityRoot} --lane ${lane}";
      description = "Forward desktop notifications (org.freedesktop.Notifications) to sinnix-capture";
    };
  };
} args
