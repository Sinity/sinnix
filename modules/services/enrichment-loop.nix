# enrichment-loop: timer -> state dump -> claude -p (enrichment-pass skill)
# -> versioned derived outputs. Independent of the sinex/polylogue stores:
# read-only on every input, writes only under /realm/data/derived/enrichment/
# (outputs) and /realm/state/enrichment/ (watermark) -- both persistent /realm
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
                # The interactive session's TMPDIR is read-only under
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
