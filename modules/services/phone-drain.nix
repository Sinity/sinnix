# Drain-on-a-schedule for everything the phone does NOT ship itself: the
# system log, the camera and Downloads mirrors, ActivityWatch, and the
# estate's events and outbox intents -- collected in the same run that pushes
# prime's glance/steering/receipts/decks down and hands the collected intents
# to sinnix-phone-dispatcher. Wraps `sinnix-phone drain`
# (scripts/sinnix-phone), which does the reachability and wifi checks and
# skips quietly when conditions aren't met; this unit only provides the
# schedule.
#
# Ambient audio left this list on 2026-08-17: the capture app uploads each
# finished chunk itself and deletes it only after prime verifies the hash,
# which is why the largest tier this used to carry is no longer here. The
# wifi gate stays -- the camera mirror can still be a large transfer.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule {
  name = "phone-drain";
  description = "Scheduled phone -> lake drain (wifi gated)";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Seconds between drain attempts. Cheap to check often -- the script itself skips instantly when conditions aren't met.";
    };
  };
  surface = {
    unit = "sinnix-phone-drain.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    # The ambient lane is NOT declared here any more: the app uploads its own
    # chunks to sinnix-phone-dispatcher, so the lane is watched beside that
    # unit (modules/services/hub.nix) rather than beside a drain that no
    # longer touches those files.
    captures = [
      # The phone's own system log, wifi-conditional like everything this unit
      # still moves: this measures whether the DRAIN is landing anything, and
      # a phone off wifi overnight is an ordinary gap rather than a fault. It
      # is adb-only, the narrower of the two transports, which is a reason for
      # a generous budget rather than a tight one.
      {
        name = "phone-logcat";
        path = "/realm/data/machine/phone/logcat";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
      }
      # Foreground app and screen unlocks, drained out of ActivityWatch
      # Android. This is the phone's half of the signal the desktop has had
      # from ActivityWatch all along, and it had been accumulating unread
      # since 2026-08-12 -- eleven days of it, because aw-android backfills
      # from UsageStatsManager and so its history predates its own install.
      # Same wifi-conditional budget as the other phone lanes.
      {
        name = "phone-activitywatch";
        path = "/realm/data/machine/phone/activitywatch";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
      }
      # The app's own event log, and the lane that actually carries the phone's
      # telemetry: battery, health (heart rate, sleep, SpO2, steps), location,
      # thermal, notifications, and the lane_blocked records that say when one
      # of those stopped and why. It reaches the lake through this drain rather
      # than the stream receiver, and was undeclared -- so the single richest
      # phone lane was the one nothing was watching.
      {
        name = "phone-estate-events";
        path = "/realm/data/machine/phone/estate/events";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { cfg, ... }:
    {
      # Signing key for the phone capture app, which produces everything this
      # drain collects (pkgs/sinnix-phone-app, docs/phone.md). Android
      # identifies an app by its signing certificate, so losing this key turns
      # every future install into a signature conflict resolvable only by
      # uninstalling -- which also discards the app's runtime grants. It is
      # deliberately outside the Nix store: a key rebuilt whenever the sources
      # change would defeat the point of a stable identity.
      sinnix.persistence.home.directories = [ ".local/share/sinnix-phone-app" ];

      # Prime's half of the phone's estate: what the drain pushes down
      # (glance, steering, receipts, decks) and the executed-intent tokens that
      # make a re-drained intent a no-op. On the NVMe volume rather than the
      # wear-limited root because the push files are rewritten every drain, and
      # under /realm/state because losing the token set would let an already
      # executed intent run a second time after a reboot.
      systemd.tmpfiles.rules = [
        "d /realm/state/sinnix-phone 0755 sinity users -"
        "d /realm/state/sinnix-phone/inbox 0755 sinity users -"
        "d /realm/state/sinnix-phone/inbox/receipts 0755 sinity users -"
        "d /realm/state/sinnix-phone/inbox/notify 0755 sinity users -"
        "d /realm/state/sinnix-phone/inbox/decks 0755 sinity users -"
        "d /realm/state/sinnix-phone/tokens 0755 sinity users -"
      ];

      systemd.user.services.sinnix-phone-drain = {
        description = "Pull phone capture lanes into the data lake, if on wifi";
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.sinnix-phone}/bin/sinnix-phone drain";
        };
      };

      systemd.user.timers.sinnix-phone-drain = {
        description = "Periodic trigger for the phone drain check";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "5min";
          OnUnitActiveSec = "${toString cfg.intervalSec}s";
          AccuracySec = "1min";
        };
      };
    };
} args
