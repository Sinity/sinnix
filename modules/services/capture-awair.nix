# capture-awair: poll the Awair Element's LOCAL API into the capture lake.
#
# The device serves unauthenticated JSON on the LAN at
# http://<ip>/air-data/latest -- no cloud account, no API key, no rate limit
# beyond politeness. It is the estate's only sensor lane covering the room
# itself rather than the machine in it.
#
# The device does not answer ICMP, so it is invisible to a plain `nmap -sn`
# sweep; find it in the router's DHCP lease table
# (`ssh sinnix-gw cat /tmp/dhcp.leases`) instead.
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
      payload="$(curl -fsS --max-time 10 "http://$host/air-data/latest")"

      # Reject a well-formed-but-empty response too: the score field is always
      # present on a healthy Element.
      echo "$payload" | jq -e 'has("score")' >/dev/null

      echo "$payload" | "$capture_bin" write \
        --capture-root "$capture_root" --lane environment
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-awair";
  description = "Awair Element air-quality capture (local API, no cloud)";
  inherit username laneDir;
  mode = "poll";
  captureName = "environment";
  cadenceSeconds = 60;
  # Unlike media or clipboard lanes, silence here is never legitimate: the
  # room always has air. A gap means the device is unplugged, off the
  # network, or the lane is broken -- all worth surfacing.
  staleAfterSeconds = 900;
  execStart = lib.concatStringsSep " " [
    "${poller}/bin/capture-awair-poll"
    cfg.host
    "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
    healthRoot
  ];
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "2min";
    accuracySec = "10s";
  };
  unitDescription = "Poll the Awair Element local API into the capture lake";
  timerDescription = "Periodic trigger for the Awair air-quality capture";
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
}) args
