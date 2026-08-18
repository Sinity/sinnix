# capture-peripherals: desk hardware telemetry -- Logitech HID++ devices and
# paired Bluetooth audio gear -- into the capture lake.
#
# Three sub-lanes, one poller:
#   - logitech: solaar has no machine-readable output, so `solaar show`'s
#     text is parsed by anchoring on the "Codename" line every real device
#     emits (parse_solaar.py). Covers the G502 mouse and G915 keyboard's
#     battery today. The "Logitech Candy" device named in earlier recon did
#     not appear in a live sysfs USB scan or `solaar show` at the time this
#     lane was written -- either it was not connected then, or it enumerates
#     under a name/bus this lane doesn't yet look at; re-probe if it needs
#     coverage.
#   - bt-battery: bluez only exposes org.bluez.Battery1 (GATT Battery
#     Service 0x180f, or HFP AT-command battery on classic headsets) when
#     `Experimental=true` (see hardware.bluetooth.settings in
#     networking.nix) -- this lane assumes that flag and reads whatever
#     bluez surfaces, rather than hand-rolling a GATT client. An empty
#     result is the normal state for a device that is paired but not
#     currently connected (buds in a closed case do not advertise).
#   - bt-audio: AVRCP's absolute-volume control surfaces as
#     org.bluez.MediaTransport1.Volume on the active transport object,
#     alongside codec/state -- confirmed live on the Ultima 40 Aktiv and
#     the WH-1000XM4 (volume writable, not just readable).
#
# One ObjectManager call (`busctl call org.bluez / ... GetManagedObjects`)
# returns bluez's whole live object tree, parsed by parse_bluez.py rather
# than walking each device path individually.
{
  mkServiceModule,
  mkCaptureLane,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  capturesRoot = config.sinnix.paths.machineRoot;
  peripheralsRoot = "${capturesRoot}/peripherals";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  cfg = config.sinnix.services.capture-peripherals;

  parseBluez = pkgs.writeText "capture-peripherals-parse-bluez.py" (
    builtins.readFile ../../pkgs/capture-peripherals/parse_bluez.py
  );
  parseSolaar = pkgs.writeText "capture-peripherals-parse-solaar.py" (
    builtins.readFile ../../pkgs/capture-peripherals/parse_solaar.py
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
    text = builtins.readFile ../../pkgs/capture-peripherals/poll.sh;
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-peripherals";
  description = "Poll Logitech HID++ and paired Bluetooth audio device telemetry into the capture lake";
  mode = "poll";
  inherit username;
  laneDir = peripheralsRoot;
  captures = [
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
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "3min";
    accuracySec = "15s";
  };
  unitDescription = "Poll Logitech + Bluetooth audio device telemetry into the capture lake";
  timerDescription = "Periodic trigger for the peripherals capture";
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
}) args
