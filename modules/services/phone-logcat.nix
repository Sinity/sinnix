# The two phone surfaces that cannot use the Sinnix app's durable dispatcher:
# Android's system log and BCR's call-recording staging area.
#
# Ambient chunks, events, outbox data, media mirrors, and prime's inbound data
# are pushed or pulled by the Sinnix app itself through sinnix-phone-dispatcher,
# spooled on-device and acknowledged by hash. Durability moved to the side that
# holds those data.
#
# logcat needs READ_LOGS. BCR is a separate privileged app, and its app-specific
# staging copy can be more complete than the later document-provider export.
# Both therefore stay an adb pull -- a transport that also works over USB when
# the network does not. New BCR calls are decoded at intake so digital silence
# becomes a failed scheduled run instead of a false-success recording.
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
  name = "phone-logcat";
  description = "Scheduled phone log and BCR-call preservation over adb";
  docs = "docs/phone.md";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = "Seconds between attempts. Cheap to check often -- the script skips instantly when adb cannot reach the phone.";
    };
  };
  surface = {
    unit = "sinnix-phone-logcat.service";
    manager = "user";
    resourceClass = "capture";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      # adb-only, which is a reason for a generous budget rather than a tight
      # one: adbd's TCP mode does not survive a reboot, so an ordinary gap
      # here is "the cable is out and the phone has rebooted", not a fault.
      {
        name = "phone-logcat";
        path = "/realm/devices/shared/phone/logcat";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
      }
      {
        # Calls are irregular, so freshness is event-driven. The timer only
        # discovers completed files when adb is reachable.
        name = "phone-calls";
        path = "/realm/devices/shared/phone/calls";
        eventDriven = true;
      }
    ];
  };
  configFn = _: {
    # Signing key for the phone capture app (pkgs/sinnix-phone-app,
    # docs/phone.md). Android identifies an app by its signing certificate, so
    # losing this key turns every future install into a signature conflict
    # resolvable only by uninstalling -- which also discards the app's runtime
    # grants. It is deliberately outside the Nix store: a key rebuilt whenever
    # the sources change would defeat the point of a stable identity.
    #
    # Declared here rather than beside the transport because this is the unit
    # that still exists on the phone's behalf; the key belongs to the app, not
    # to any one lane.
    sinnix.persistence.home.directories = [ ".local/share/sinnix-phone-app" ];
  };
  job =
    { cfg, ... }:
    {
      description = "Pull the phone's system log and preserve BCR calls";
      manager = "user";
      execStart = "${scriptPkgs.sinnix-phone}/bin/sinnix-phone logcat";
      timer = {
        onBootSec = "5min";
        intervalSec = cfg.intervalSec;
        accuracySec = "1min";
      };
    };
} args
