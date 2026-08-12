# Desktop notification capture lane (sinnix-sz0c)
#
# Reference instance of the event-capture-lane template: mkServiceModule
# default-off, user-manager daemon, capture-runtime resource class, writing
# through the shared sinnix-capture envelope library
# (pkgs/sinnix-capture). Future lanes (clipboard, hyprland events, ...)
# should copy this file's shape rather than re-deriving it.
#
# The daemon itself is `scripts/sinnix-capture-notifications-listener`: it
# runs `busctl --user monitor --json=short org.freedesktop.Notifications`
# (systemd, already vendored -- no new dbus-python/dbus-next dependency)
# and forwards each Notify() call -- app_name, summary, body, urgency,
# actions, timestamp -- to `sinnix-capture write --lane notifications`.
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
    kind = "capture";
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
        # sentinel's only signal (see modules/runtime.nix). The plan's
        # original ~3600s figure assumed roughly hourly notification
        # traffic; desktop notifications are legitimately bursty and can go
        # silent for many hours (screen off, DND, a quiet afternoon) without
        # anything being wrong, so a 1h budget would false-positive
        # routinely. 86400s (daily) matches terminal-capture's asciinema
        # lane -- the other session-driven, cadence-less capture lane in
        # this repo -- and both share the same "did anything write today"
        # framing (sinnix-sz0c judgment call).
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { pkgs, ... }:
    {
      # laneDir lives under /realm (already a persistent, non-impermanence
      # volume -- see modules/persistence.nix, which only governs bind
      # mounts from /persist into the ephemeral @ root). No
      # sinnix.persistence entry is needed here, matching every other
      # capture lane under capturesRoot (core.nix's tmpfiles rules, not
      # persistence.nix, provision those directories).
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${userName} users -"
      ];

      home-manager.users.${userName} = {
        systemd.user.services.sinnix-capture-notifications = {
          Unit = {
            Description = "Forward desktop notifications (org.freedesktop.Notifications) to sinnix-capture";
            After = [ "default.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${listener}/bin/sinnix-capture-notifications-listener --capture-bin ${captureCli}/bin/sinnix-capture --capture-root ${config.sinnix.paths.capturesRoot} --lane ${lane}";
            Restart = "on-failure";
            RestartSec = "5s";
            NoNewPrivileges = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [ laneDir ];
          };
          Install.WantedBy = [ "default.target" ];
        };
      };
    };
} args
