# capture-awair: poll the Awair Element's LOCAL API into the capture lake.
#
# The device serves unauthenticated JSON on the LAN at
# http://<ip>/air-data/latest -- no cloud account, no API key, no rate limit
# beyond politeness. That makes air quality one of the cheapest real sensor
# streams available to the estate, and it is the only one covering the room
# itself rather than the machine in it.
#
# Discovery note: the device does not answer ICMP and so is invisible to a
# plain `nmap -sn` sweep; it was found in the router's DHCP lease table
# (`ssh sinnix-gw cat /tmp/dhcp.leases`). Prefer the lease table over a ping
# sweep when hunting for IoT endpoints on this network.
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
  laneDir = "${capturesRoot}/awair";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

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
        --capture-root "$capture_root" --lane awair
    '';
  };
in
mkServiceModule {
  name = "capture-awair";
  description = "Awair Element air-quality capture (local API, no cloud)";
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
  surface = {
    unit = "sinnix-capture-awair.service";
    manager = "user";
    # No explicit kind: the surface is the oneshot .service (the timer only
    # triggers it), so the default "service" is correct and the suffix
    # assertion in modules/runtime.nix enforces exactly that.
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "awair";
        path = laneDir;
        expectedCadenceSeconds = 60;
        # Unlike media or clipboard lanes, silence here is never legitimate:
        # the room always has air. A gap means the device is unplugged, off
        # the network, or the lane is broken -- all worth surfacing.
        staleAfterSeconds = 900;
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
          systemd.user.services.sinnix-capture-awair = {
            Unit.Description = "Poll the Awair Element local API into the capture lake";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-awair.service";
              overrides = {
                Type = "oneshot";
                ExecStart = lib.concatStringsSep " " [
                  "${poller}/bin/capture-awair-poll"
                  cfg.host
                  "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
                  capturesRoot
                ];
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [ laneDir ];
                # The session TMPDIR is read-only inside this namespace; see
                # the clipboard lane's fix for the same trap.
                Environment = [ "TMPDIR=/tmp" ];
                PrivateTmp = true;
              };
            };
          };

          systemd.user.timers.sinnix-capture-awair = {
            Unit.Description = "Periodic trigger for the Awair air-quality capture";
            Timer = {
              OnBootSec = "2min";
              OnUnitActiveSec = "${toString cfg.intervalSec}s";
              AccuracySec = "10s";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
