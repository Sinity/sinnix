# Drain-on-a-schedule for the phone lanes, gated on wifi rather than pulled
# manually. Bidirectional since the app became the estate's phone-side member:
# the same run collects chunks, events and outbox intents, pushes prime's
# glance/steering/receipts/decks down, and hands the collected intents to
# sinnix-phone-dispatcher. Wraps `sinnix-phone drain` (scripts/sinnix-phone),
# which does the actual reachability/wifi checks and skips quietly when
# conditions aren't met -- this unit only provides the schedule. The wifi
# gate is deliberate: this is the large/opportunistic raw-audio tier, not a
# small always-on VAD-gated stream.
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
    # A dead phone mic and a quiet room are otherwise indistinguishable, so
    # this watches the LAKE side (did the drain land a new chunk) rather than
    # the phone-side recorder. The threshold is generous because the drain is
    # wifi-conditional: a phone off wifi for hours is a real, non-alarming
    # gap, not evidence the mic died.
    captures = [
      {
        name = "phone-ambient";
        path = "/realm/data/captures/phone/ambient";
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
