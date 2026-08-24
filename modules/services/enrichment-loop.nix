# enrichment-loop: timer -> state dump -> claude -p (enrichment-pass skill)
# -> versioned derived outputs. Independent of the sinex/polylogue stores:
# read-only on every input, writes only under /realm/data/derived/reports/enrichment/
# (outputs) and /realm/state/cursors/enrichment/ (watermark) -- both persistent /realm
# NVMe paths, not the ephemeral root subvolume, so tmpfiles rules suffice and
# no impermanence entry is needed.
#
# This is derived data, not raw capture, so the runtime surface carries no
# `captures[]` entry: outputs are re-derivable from their inputs, so a lost
# run is not the kind of gap the capture-staleness sentinel exists to catch.
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
  homeDir = "/home/${username}";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  dump = scriptPkgs.sinnix-enrich-dump;
  stateDir = "/realm/state/cursors/enrichment";
  outputRoot = "/realm/data/derived/reports/enrichment";
in
mkServiceModule {
  name = "enrichment-loop";
  description = "Hourly system state-dump -> enrichment-pass -> versioned derived outputs";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 60;
      description = "Minutes between enrichment passes.";
    };
  };
  surface = {
    unit = "sinnix-enrichment-loop.service";
    manager = "user";
    resourceClass = "background-maintenance";
    observe.enable = true;
  };
  configFn = _: {
    environment.systemPackages = [ dump ];
    systemd.tmpfiles.rules = [
      "d ${stateDir} 0700 ${username} users -"
      "d ${outputRoot} 0755 ${username} users -"
    ];
  };
  # NixOS-level systemd.user (via the factory) rather than the previous
  # home-manager.users.${username} block: this moves the rendered fragment
  # from ~/.config/systemd/user to /etc/systemd/user, but
  # modules/runtime.nix's OnFailure drop-in mechanism already handles both
  # namespaces, and the service is disabled on sinnix-prime
  # (hosts/sinnix-prime/default.nix), so this is render-only. `dump` reaches
  # PATH via environment.systemPackages above; the previous home.packages
  # entry was redundant with it.
  job =
    { cfg, lib, ... }:
    {
      manager = "user";
      resourceClass = "background-maintenance";
      description = "Enrichment pass: dump system state, run claude -p, write versioned outputs";
      execStart = "${dump}/bin/sinnix-enrich-dump";
      # The interactive session's TMPDIR is read-only under
      # ProtectSystem=strict, so mktemp needs its own writable tmp.
      environment = {
        TMPDIR = "/tmp";
      };
      serviceConfig = {
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        # Off so claude can write its session transcript; the write
        # surface is ReadWritePaths, which ProtectSystem=strict pins.
        ProtectHome = false;
        ReadWritePaths = [
          stateDir
          outputRoot
          # bd rewrites its store on export, so a read-only steering
          # workspace makes that input fail rather than be absent.
          "/realm/project/steering"
        ]
        ++ lib.sinnix.systemd.agentRuntimeWritePaths { home = homeDir; };
        # Clear of the observed run distribution (healthy passes run
        # 1-3min) but under the hourly interval, so a slow pass still
        # cannot overlap its successor.
        TimeoutStartSec = "600s";
      };
      timer = {
        onBootSec = "5min";
        onUnitActiveSec = "${toString cfg.intervalMinutes}min";
        accuracySec = "1min";
        description = "Periodic trigger for the enrichment loop";
      };
    };
} args
