# capture-router: pull the router's own evidence of the network into the lake.
#
# sinnix-gw is sinnix's only whole-network vantage point. It collects
# four kinds of signal locally:
#   - a persistent syslog (/overlay/log/syslog + .old) that otherwise rotates
#     away unharvested (dropbear auth, dnsmasq, hostapd, netifd events);
#   - nlbwmon per-device bandwidth history in /overlay/nlbwmon -- NOT
#     /var/lib/nlbwmon, which the stock anonymous UCI section points at and
#     which sits empty; the named `nlbwmon` section repoints
#     database_directory at the overlay;
#   - the DHCP lease table (/tmp/dhcp.leases, volatile -- lost on reboot);
#   - per-AP wifi association state via `ubus call hostapd.<ap> get_clients`,
#     carrying signal strength, kept unbucketed as a presence signal.
#
# The R6220 is a 128MB-RAM MT7621 whose CPU budget already forced fq_codel
# over CAKE (see hosts/sinnix-gw/default.nix), so this lane PULLS from prime
# over ssh on an infrequent timer rather than running or installing anything
# on the router, and it never touches dnsmasq query logging -- full DNS query
# logs are both the CPU-heaviest and the most sensitive stream on the network.
#
# See pkgs/capture-router/ for the poller (poll.sh, run locally on prime) and
# the two remote scripts it pipes over ssh (remote-poll.sh,
# remote-periods.sh); their headers document syslog rotation safety and the
# nlbwmon once-per-closed-month backfill.
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
  lakeRoot = config.sinnix.paths.machineRoot;
  routerRoot = "${lakeRoot}/router";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  cfg = config.sinnix.services.capture-router;

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
mkServiceModule (mkCaptureLane {
  name = "capture-router";
  description = "Pull sinnix-gw's syslog, nlbwmon, DHCP leases, and wifi associations into the capture lake";
  extraOptions = {
    host = lib.mkOption {
      type = lib.types.str;
      default = "192.168.1.1";
      description = ''
        ssh target for the router: the address itself, not the operator's
        `sinnix-gw` alias. The lane deliberately runs ssh with -F /dev/null
        and an explicit identity, because under its ProtectHome sandbox ssh
        refuses the Home-Manager ~/.ssh/config ("Bad owner or permissions",
        exit 255) -- and because a capture lane should behave the same
        whether a timer or a human invokes it. No new credential is
        introduced; it reuses the operator's existing key.
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
  mode = "poll";
  inherit username;
  laneDir = routerRoot;
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
  execStart = lib.concatStringsSep " " [
    "${poller}/bin/capture-router-poll"
    cfg.host
    "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
    routerRoot
    "${remotePollScript}"
    "${remotePeriodsScript}"
  ];
  # ssh needs a real TMPDIR for its own scratch use, and the session TMPDIR
  # is read-only inside this namespace.
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "5min";
    accuracySec = "30s";
  };
  unitDescription = "Pull sinnix-gw telemetry (syslog, nlbwmon, leases, associations) into the capture lake";
  timerDescription = "Periodic trigger for the router telemetry capture";
}) args
