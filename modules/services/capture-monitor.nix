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
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  lakeRoot = config.sinnix.paths.machineRoot;
  laneDir = "${lakeRoot}/monitor";
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

      # One getvcp call avoids repeated I2C probes; no VCP lines means an outage and exits non-zero.
      # Brief output differs for continuous and simple features, so match each line by its code.
      vcp="$(ddcutil getvcp 10 12 d6 60 --brief 2>/dev/null)"
      echo "$vcp" | grep -q '^VCP ' || {
        echo "capture-monitor: no DDC/CI answer from the display" >&2
        exit 1
      }
      read_vcp() {
        local raw
        raw="$(echo "$vcp" | awk -v code="$1" 'toupper($2) == toupper(code) {print $4}')"
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
mkServiceModule {
  name = "capture-monitor";
  description = "AORUS FO48U DDC/CI sensor capture: power state, brightness/contrast drift, input source";
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
  configFn = _: {
    sinnix.capture.producers.capture-monitor = {
      directories = [ laneDir ];
      outputs = [
        {
          path = laneDir;
          name = "monitor";
          cadenceSeconds = cfg.intervalSec;
          # A gap here means the panel is off, unplugged, or DDC broke -- all worth
          # surfacing, but on a slower clock than a live sensor: normal sleep/wake
          # or an input switch can legitimately silence a poll or two.
          staleAfterSeconds = 3600;
        }
      ];
      execStart = lib.concatStringsSep " " [
        "${poller}/bin/capture-monitor-poll"
        "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
        lakeRoot
      ];
      # /dev/i2c-* is group-owned (i2c) and the service inherits the operator's
      # supplementary groups via systemd --user, so no DeviceAllow is needed as
      # long as PrivateDevices stays unset.
      poll.timer = {
        intervalSec = cfg.intervalSec;
        onBootSec = "3min";
        accuracySec = "30s";
      };
      description = "Poll the AORUS FO48U over DDC/CI into the capture lake";
      poll.timer.description = "Periodic trigger for the monitor DDC/CI capture";
    };
  };
} args
