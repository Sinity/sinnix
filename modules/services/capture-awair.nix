# capture-awair: poll the Awair Element's LOCAL API into the capture lake.
#
# The device serves unauthenticated JSON on the LAN at
# http://<ip>/air-data/latest -- no cloud account, no API key, no rate limit
# beyond politeness. It is sinnix's only sensor lane covering the room
# itself rather than the machine in it.
#
# The device does not answer ICMP, so it is invisible to a plain `nmap -sn`
# sweep; find it in the router's DHCP lease table
# (`ssh sinnix-gw cat /tmp/dhcp.leases`) instead.
{
  mkServiceModule,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  inherit (config.sinnix.paths) healthRoot;
  laneDir = "${healthRoot}/environment";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  cfg = config.sinnix.services.capture-awair;

  poller = pkgs.writeShellApplication {
    name = "capture-awair-poll";
    runtimeInputs = [
      pkgs.curl
      pkgs.jq
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      host="$1"
      capture_bin="$2"
      capture_root="$3"

      # A sensor that stops answering must look like an outage, never like a
      # calm room -- so a failed poll exits non-zero (surfacing in the unit's
      # state) rather than writing a zero-valued record.
      # A normal sensor document is a few hundred bytes. Refuse oversized
      # responses before parsing, including bodies without Content-Length.
      # Keep the response out of shell memory and never capture a partial body.
      payload_file="$(mktemp)"
      trap 'unlink -- "$payload_file"' EXIT
      curl -fsS --max-time 10 --max-filesize 1048576 \
        --output "$payload_file" "http://$host/air-data/latest"

      # Reject a well-formed-but-empty response too: the score field is always
      # present on a healthy Element.
      jq -e 'has("score")' "$payload_file" >/dev/null

      "$capture_bin" write \
        --capture-root "$capture_root" --lane environment < "$payload_file"
    '';
  };
in
mkServiceModule {
  name = "capture-awair";
  description = "Awair Element air-quality capture (local API, no cloud)";
  configFn = _: {
    sinnix.capture.producers.capture-awair = {
      directories = [ laneDir ];
      outputs = [
        {
          name = "environment";
          path = laneDir;
          cadenceSeconds = cfg.intervalSec;
          # Unlike media or clipboard lanes, silence here is never legitimate: the
          # room always has air. A gap means the device is unplugged, off the
          # network, or the lane is broken -- all worth surfacing.
          staleAfterSeconds = 900;
        }
      ];
      execStart = lib.concatStringsSep " " [
        "${poller}/bin/capture-awair-poll"
        cfg.host
        "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
        healthRoot
      ];
      poll.timer = {
        intervalSec = cfg.intervalSec;
        onBootSec = "2min";
        accuracySec = "10s";
      };
      description = "Poll the Awair Element local API into the capture lake";
      poll.timer.description = "Periodic trigger for the Awair air-quality capture";
    };
  };
  extraOptions = {
    host = lib.mkOption {
      type = lib.types.str;
      default = "192.168.1.52";
      description = ''
        LAN address of the Awair Element. Static-lease it on the router if it
        ever moves; the device has no mDNS name this host can rely on.
      '';
    };
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = ''
        Seconds between polls. The device updates its own readings roughly
        every 10s; 60s keeps the lane cheap while still resolving the
        occupancy-driven CO2 swings that make this data interesting.
      '';
    };
  };
} args
