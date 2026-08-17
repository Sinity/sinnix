# capture-monitor: poll the AORUS FO48U over DDC/CI into the capture lake.
#
# Treats the monitor as a sensor: VCP 0xD6 (power mode) turns "is the screen
# on" from an inference into a measurement that joins to ActivityWatch idle
# state; 0x10/0x12 (brightness/contrast) drift evidences ASBL directly; 0x60
# (input source) records which machine currently owns the panel.
#
# ddcutil is slow -- each VCP read/write is a real i2c transaction, observed
# at ~0.5-0.6s round-trip on this host, and a poll needs four of them. Keep
# the interval generous; this is not a lane to tighten for freshness.
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
  laneDir = "${capturesRoot}/monitor";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  cfg = config.sinnix.services.capture-monitor;

  poller = pkgs.writeShellApplication {
    name = "capture-monitor-poll";
    runtimeInputs = [
      pkgs.ddcutil
      pkgs.jq
      pkgs.gnugrep
      pkgs.gawk
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      capture_bin="$1"
      capture_root="$2"

      # A monitor that stops answering DDC (cable unplugged, panel off,
      # input switched to a source with no i2c passthrough) must look like
      # an outage, not a calm reading -- so a failed detect exits non-zero.
      detect="$(ddcutil detect --brief 2>&1)"
      echo "$detect" | grep -q '^Display 1' || {
        echo "capture-monitor: ddcutil detect found no display" >&2
        exit 1
      }

      # --brief has two shapes depending on VCP feature type:
      #   continuous (0x10, 0x12):     "VCP 10 C 50 100"   -- $4 is decimal
      #   simple non-continuous (0xd6, 0x60): "VCP D6 SNC x01" -- $4 is hex
      read_vcp() {
        local raw
        raw="$(ddcutil getvcp "$1" --brief 2>/dev/null | awk '{print $4}')"
        if [[ "$raw" == x* ]]; then
          printf '%d' "0x''${raw#x}"
        else
          echo "$raw"
        fi
      }

      brightness="$(read_vcp 10)"
      contrast="$(read_vcp 12)"
      power_sl="$(read_vcp d6)"
      input_sl="$(read_vcp 60)"

      jq -n \
        --arg brightness "$brightness" \
        --arg contrast "$contrast" \
        --arg power_sl "$power_sl" \
        --arg input_sl "$input_sl" \
        '{
          brightness: ($brightness | tonumber? // null),
          contrast: ($contrast | tonumber? // null),
          power_sl: ($power_sl | tonumber? // null),
          input_sl: ($input_sl | tonumber? // null)
        }' | "$capture_bin" write --capture-root "$capture_root" --lane monitor
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-monitor";
  description = "AORUS FO48U DDC/CI sensor capture: power state, brightness/contrast drift, input source";
  inherit username laneDir;
  mode = "poll";
  captureName = "monitor";
  cadenceSeconds = 300;
  # A gap here means the panel is off, unplugged, or DDC broke -- all worth
  # surfacing, but on a slower clock than a live sensor: normal sleep/wake
  # or an input switch can legitimately silence a poll or two.
  staleAfterSeconds = 3600;
  execStart = lib.concatStringsSep " " [
    "${poller}/bin/capture-monitor-poll"
    "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
    capturesRoot
  ];
  # /dev/i2c-* is group-owned (i2c) and the service inherits the operator's
  # supplementary groups via systemd --user, so no DeviceAllow is needed as
  # long as PrivateDevices stays unset.
  #
  # ddcutil persists its dynamic-sleep-adjustment table under
  # $XDG_CACHE_HOME/ddcutil, and ProtectHome=read-only makes that write fail
  # on every single VCP access -- five "Read-only file system" errors per
  # poll, forever, and a DSA table that can never carry timing knowledge
  # from one poll to the next. Point the cache at the runtime dir, which
  # survives across runs of this oneshot and is the only writable location
  # the sandbox leaves it.
  environment = [
    "TMPDIR=/tmp"
    "XDG_CACHE_HOME=%t/sinnix-capture-monitor"
  ];
  runtimeDirectory = "sinnix-capture-monitor";
  runtimeDirectoryPreserve = "yes";
  privateTmp = true;
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "3min";
    accuracySec = "30s";
  };
  unitDescription = "Poll the AORUS FO48U over DDC/CI into the capture lake";
  timerDescription = "Periodic trigger for the monitor DDC/CI capture";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = ''
        Seconds between polls. Each poll costs ~2-3s of real i2c transaction
        time (four ddcutil round-trips); keep this well above that and above
        any value that would make DDC polling itself a visible interruption.
      '';
    };
  };
}) args
