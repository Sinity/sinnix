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
  username = config.sinnix.user.name;
  inherit (config.sinnix.paths) capturesRoot;
  laneDir = "${capturesRoot}/monitor";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

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
  surface = {
    unit = "sinnix-capture-monitor.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "monitor";
        path = laneDir;
        cadenceSeconds = 300;
        # A gap here means the panel is off, unplugged, or DDC broke --
        # all worth surfacing, but on a slower clock than a live sensor:
        # normal sleep/wake or an input switch can legitimately silence a
        # poll or two.
        staleAfterSeconds = 3600;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0755 ${username} users -"
      ];

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services.sinnix-capture-monitor = {
            Unit.Description = "Poll the AORUS FO48U over DDC/CI into the capture lake";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-monitor.service";
              overrides = {
                Type = "oneshot";
                ExecStart = lib.concatStringsSep " " [
                  "${poller}/bin/capture-monitor-poll"
                  "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
                  capturesRoot
                ];
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [ laneDir ];
                # /dev/i2c-* is group-owned (i2c) and the service inherits the
                # operator's supplementary groups via systemd --user, so no
                # DeviceAllow is needed as long as PrivateDevices stays unset.
                Environment = [ "TMPDIR=/tmp" ];
                PrivateTmp = true;
              };
            };
          };

          systemd.user.timers.sinnix-capture-monitor = {
            Unit.Description = "Periodic trigger for the monitor DDC/CI capture";
            Timer = {
              OnBootSec = "3min";
              OnUnitActiveSec = "${toString cfg.intervalSec}s";
              AccuracySec = "30s";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
