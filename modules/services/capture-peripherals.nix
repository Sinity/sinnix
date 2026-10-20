# Poll Logitech HID++ battery and BlueZ battery/audio transport records.
# Solaar output is parsed by Codename; BlueZ uses one ObjectManager snapshot.
# Battery1 availability requires BlueZ experimental features (networking.nix).
# Disconnected devices and inactive transports legitimately produce no records.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  peripheralsRoot = config.sinnix.paths.machinePaths.peripheral;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  cfg = config.sinnix.services.capture-peripherals;

  parseBluez = pkgs.writeText "capture-peripherals-parse-bluez.py" (
    builtins.readFile ../../pkgs/sinnix-capture-peripherals/parse_bluez.py
  );
  parseSolaar = pkgs.writeText "capture-peripherals-parse-solaar.py" (
    builtins.readFile ../../pkgs/sinnix-capture-peripherals/parse_solaar.py
  );

  poller = pkgs.writeShellApplication {
    name = "capture-peripherals-poll";
    runtimeInputs = [
      pkgs.solaar
      pkgs.systemd # busctl
      pkgs.jq
      pkgs.python3
      pkgs.coreutils
    ];
    text = builtins.readFile ../../pkgs/sinnix-capture-peripherals/poll.sh;
  };
in
mkServiceModule {
  name = "capture-peripherals";
  description = "Poll Logitech HID++ and paired Bluetooth audio device telemetry into the capture lake";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = ''
        Seconds between polls. HID++ battery and AVRCP volume both drift
        slowly (hours, not seconds), so this stays well above the desktop
        session lanes' cadence.
      '';
    };
  };
  configFn = _: {
    sinnix.capture.producers.capture-peripherals = {
      directories = [ peripheralsRoot ];
      outputs = [
        {
          name = "peripherals-logitech";
          path = "${peripheralsRoot}/logitech";
          cadenceSeconds = cfg.intervalSec;
          # A receiver with nothing paired, or an empty result if solaar sees
          # no receiver at all, is a legitimate desk state -- staleness here
          # only means the poll itself stopped happening.
          staleAfterSeconds = cfg.intervalSec * 4;
        }
        {
          name = "peripherals-bt-battery";
          path = "${peripheralsRoot}/bt-battery";
          cadenceSeconds = cfg.intervalSec;
          # No staleAfterSeconds: an empty battery[] array is the normal state
          # whenever every paired audio device is out of range or powered off
          # (closed earbuds case, speaker unplugged), which is common and not
          # a lane failure -- unlike capture-awair's always-on room sensor.
        }
        {
          name = "peripherals-bt-audio";
          path = "${peripheralsRoot}/bt-audio";
          cadenceSeconds = cfg.intervalSec;
          # Same reasoning: no transport is active whenever nothing is
          # currently streaming audio to a Bluetooth sink.
        }
      ];
      execStart = lib.concatStringsSep " " [
        "${poller}/bin/capture-peripherals-poll"
        "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
        peripheralsRoot
        "${parseBluez}"
        "${parseSolaar}"
      ];
      poll.timer = {
        intervalSec = cfg.intervalSec;
        onBootSec = "3min";
        accuracySec = "15s";
      };
      description = "Poll Logitech + Bluetooth audio device telemetry into the capture lake";
      poll.timer.description = "Periodic trigger for the peripherals capture";
    };
  };
} args
