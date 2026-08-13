# enrichment-loop: timer -> state dump -> claude -p (enrichment-pass skill)
# -> versioned derived outputs (sinnix-jfiy.2, first concrete increment of
# sinnix-qa2s). Deliberately sinex/polylogue-store-independent (2026-08-11
# fork verdict): read-only on every input, writes only under
# /realm/data/derived/enrichment/ (outputs) and /realm/state/enrichment/
# (watermark) -- both persistent /realm NVMe paths, not the ephemeral root
# subvolume, so tmpfiles rules suffice (no impermanence entry needed, same
# reasoning as capture-awair/steering).
#
# This is derived data, not raw capture -- no `captures[]` entry on the
# runtime surface (that field is for the capture-lane staleness sentinel;
# outputs here are re-derivable from their inputs by design, so losing a run
# is not the kind of gap that sentinel exists to catch).
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
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  dump = scriptPkgs.sinnix-enrich-dump;
  stateDir = "/realm/state/enrichment";
  outputRoot = "/realm/data/derived/enrichment";
in
mkServiceModule {
  name = "enrichment-loop";
  description = "Hourly estate state-dump -> enrichment-pass -> versioned derived outputs";
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
  configFn =
    { cfg, config, ... }:
    {
      environment.systemPackages = [ dump ];
      systemd.tmpfiles.rules = [
        "d ${stateDir} 0700 ${username} users -"
        "d ${outputRoot} 0755 ${username} users -"
      ];

      home-manager.users.${username} =
        { ... }:
        {
          home.packages = [ dump ];

          systemd.user.services.sinnix-enrichment-loop = {
            Unit.Description = "Enrichment pass: dump estate state, run claude -p, write versioned outputs";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-enrichment-loop.service";
              overrides = {
                Type = "oneshot";
                ExecStart = "${dump}/bin/sinnix-enrich-dump";
                # Same sandbox-vs-TMPDIR trap as every other capture-class
                # lane this session hit (clipboard, primary, awair): the
                # interactive session's TMPDIR is read-only under
                # ProtectSystem=strict, so mktemp needs its own writable tmp.
                Environment = [ "TMPDIR=/tmp" ];
                PrivateTmp = true;
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [
                  stateDir
                  outputRoot
                ];
                # 3-minute budget: a `claude -p` round trip plus dump/verify
                # overhead comfortably fits; a wedged invocation should not
                # hold the scope open indefinitely.
                TimeoutStartSec = "180s";
              };
            };
          };
          systemd.user.timers.sinnix-enrichment-loop = {
            Unit.Description = "Periodic trigger for the enrichment loop";
            Timer = {
              OnBootSec = "5min";
              OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
              AccuracySec = "1min";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
