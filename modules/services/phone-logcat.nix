# The one thing the phone cannot push: its own system log.
#
# This unit is what is left of sinnix-phone-drain. Everything that drain used
# to move -- ambient chunks, the event log, outbox intents and blobs, the
# camera and Downloads mirrors, and prime's own glance/steering/receipts/decks
# going the other way -- is now pushed or pulled by the app itself through
# sinnix-phone-dispatcher, spooled on the device and acknowledged by hash.
# Durability moved to the side that holds the data.
#
# `logcat` did not move, and cannot: reading another app's log needs
# READ_LOGS, which Android grants to system and privileged apps only, and this
# app is neither on a locked-bootloader device. So the log stays a pull over
# adb -- a transport that works over USB when no network does -- on a timer,
# which is exactly what this unit is and all it is.
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
  description = "Scheduled phone system-log pull over adb";
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
    resourceClass = "capture-runtime";
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
        path = "/realm/data/machine/phone/logcat";
        cadenceSeconds = 1800;
        staleAfterSeconds = 86400;
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
      description = "Pull the phone's system log into the data lake";
      manager = "user";
      execStart = "${scriptPkgs.sinnix-phone}/bin/sinnix-phone logcat";
      timer = {
        onBootSec = "5min";
        intervalSec = cfg.intervalSec;
        accuracySec = "1min";
      };
    };
} args
