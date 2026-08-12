# capture-router: pull the router's own evidence of the network into the
# lake (sinnix-zihb).
#
# sinnix-gw is the estate's only whole-network vantage point -- every
# device's traffic passes through it -- and until this lane, none of that
# was kept anywhere. It already collects real signal locally:
#   - a persistent syslog (/overlay/log/syslog + .old) that simply rotates
#     away unharvested (dropbear auth, dnsmasq, hostapd, netifd events);
#   - nlbwmon, with real longitudinal per-device bandwidth history already
#     sitting in /overlay/nlbwmon (NOT /var/lib/nlbwmon, which the default
#     anonymous UCI section points at and sits empty -- a live footgun in
#     the stock config that the named `nlbwmon` section works around by
#     pointing database_directory at the overlay instead);
#   - the DHCP lease table (/tmp/dhcp.leases, volatile -- lost on reboot);
#   - per-AP wifi association state via `ubus call hostapd.<ap>
#     get_clients`, which carries signal strength -- a real presence/
#     room-location signal, kept as-is (not bucketed) per the design brief.
#
# The R6220 is a 128MB-RAM MT7621 whose CPU budget already forced fq_codel
# over CAKE (see hosts/sinnix-gw/default.nix), so this lane PULLS from prime
# over ssh on an infrequent timer rather than running or installing anything
# on the router, and it never touches dnsmasq query logging -- full DNS
# query logs are both the CPU-heaviest and the single most sensitive stream
# on the network.
#
# See pkgs/capture-router/ for the poller (poll.sh, run locally on prime)
# and the two remote scripts it pipes over ssh (remote-poll.sh,
# remote-periods.sh) -- their headers document the syslog rotation-safety
# design and the nlbwmon once-per-closed-month backfill, both verified
# against the live router 2026-08-13.
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
  routerRoot = "${capturesRoot}/router";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  remotePollScript = pkgs.writeText "capture-router-remote-poll.sh" (
    builtins.readFile ../../pkgs/capture-router/remote-poll.sh
  );
  remotePeriodsScript = pkgs.writeText "capture-router-remote-periods.sh" (
    builtins.readFile ../../pkgs/capture-router/remote-periods.sh
  );

  poller = pkgs.writeShellApplication {
    name = "capture-router-poll";
    runtimeInputs = [
      pkgs.openssh
      pkgs.jq
      pkgs.gawk
      pkgs.coreutils
      pkgs.gnused
    ];
    text = builtins.readFile ../../pkgs/capture-router/poll.sh;
  };
in
mkServiceModule {
  name = "capture-router";
  description = "Pull sinnix-gw's syslog, nlbwmon, DHCP leases, and wifi associations into the capture lake";
  extraOptions = {
    host = lib.mkOption {
      type = lib.types.str;
      default = "sinnix-gw";
      description = ''
        ssh target for the router. Uses the operator's existing key-authed
        `sinnix-gw` alias -- no new credential or config is introduced by
        this lane.
      '';
    };
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1800;
      description = ''
        Seconds between polls. The router is a 128MB-RAM MT7621 that
        already gave up CAKE for fq_codel on CPU grounds (see
        hosts/sinnix-gw/default.nix); this lane pulls over ssh from prime
        rather than running anything on the router, and 30 minutes keeps
        even that pull invisible while still resolving syslog rotation
        (log_size=512KB, observed to cover several days of this network's
        volume) well within one interval.
      '';
    };
  };
  surface = {
    unit = "sinnix-capture-router.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "router-leases";
        path = "${routerRoot}/leases";
        cadenceSeconds = 1800;
        # Leases are a volatile snapshot (lost on router reboot); a gap
        # here means the lane broke or the router is unreachable, not that
        # nothing happened, since some lease always exists once any device
        # has ever joined.
        staleAfterSeconds = 7200;
      }
      {
        name = "router-associations";
        path = "${routerRoot}/associations";
        cadenceSeconds = 1800;
        # An empty association list is completely normal (nobody home /
        # everyone off wifi) -- but the poll itself still always produces a
        # record, empty or not, so staleness here still correctly means
        # "the poll stopped happening".
        staleAfterSeconds = 7200;
      }
      {
        name = "router-nlbw";
        path = "${routerRoot}/nlbw";
        cadenceSeconds = 1800;
        staleAfterSeconds = 7200;
      }
      {
        name = "router-syslog";
        path = "${routerRoot}/syslog";
        cadenceSeconds = 1800;
        # No staleAfterSeconds: genuinely silent intervals are normal on a
        # quiet home LAN, and poll.sh deliberately writes no envelope at
        # all for an empty syslog delta (unlike the other three sub-lanes),
        # so cadence-based staleness would false-positive on ordinary quiet
        # nights rather than signal a broken lane.
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${routerRoot} 0755 ${username} users -"
      ];

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services.sinnix-capture-router = {
            Unit.Description = "Pull sinnix-gw telemetry (syslog, nlbwmon, leases, associations) into the capture lake";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-router.service";
              overrides = {
                Type = "oneshot";
                ExecStart = lib.concatStringsSep " " [
                  "${poller}/bin/capture-router-poll"
                  cfg.host
                  "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
                  routerRoot
                  "${remotePollScript}"
                  "${remotePeriodsScript}"
                ];
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [ routerRoot ];
                # ssh needs a real TMPDIR for its own scratch use, and the
                # session TMPDIR is read-only inside this namespace -- same
                # trap documented in the clipboard and awair lanes.
                Environment = [ "TMPDIR=/tmp" ];
                PrivateTmp = true;
              };
            };
          };

          systemd.user.timers.sinnix-capture-router = {
            Unit.Description = "Periodic trigger for the router telemetry capture";
            Timer = {
              OnBootSec = "5min";
              OnUnitActiveSec = "${toString cfg.intervalSec}s";
              AccuracySec = "30s";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
