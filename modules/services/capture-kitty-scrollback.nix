# Periodic kitty terminal scrollback capture (sinnix-9pd Phase 3a, 3.5)
#
# scripts/kitty-scrollback-capture (full-ANSI-fidelity scrollback dump via
# `kitty @ get-text`) existed only as a manually-triggered PATH script --
# nothing ever ran it, so the "kitty-scrollback" lane registered in
# capture-registry.nix was permanently stale despite that registry's
# staleAfterSeconds implying a roughly-daily cadence. This module revives
# it as a real capture surface: a systemd --user timer runs the same
# script on a fixed cadence, replacing the orphan registry entry (which
# is removed from capture-registry.nix in the same change) with a real
# owning unit the health sentinel can actually track.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  capturesRoot = config.sinnix.paths.capturesRoot;
  scrollbackDir = "${capturesRoot}/kitty-scrollback";
in
mkServiceModule {
  name = "capture-kitty-scrollback";
  description = "Periodic full-ANSI kitty terminal scrollback capture";
  extraOptions = {
    intervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 30;
      description = "Minutes between scrollback capture runs.";
    };
  };
  surface = {
    unit = "sinnix-capture-kitty-scrollback.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = false;
    };
    captures = [
      {
        name = "kitty-scrollback";
        path = scrollbackDir;
        eventDriven = true;
        # Same staleness budget as the orphan entry this replaces --
        # no kitty windows open for a full day is itself a real signal
        # (host idle/away), not just a quiet capture lane.
        staleAfterSeconds = 86400;
      }
    ];
  };
  configFn =
    { cfg, config, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${scrollbackDir} 0755 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-kitty-scrollback = {
          Unit = {
            Description = "Full-ANSI kitty terminal scrollback capture";
            After = [ "graphical-session.target" ];
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-kitty-scrollback.service";
            overrides = {
              Type = "oneshot";
              Environment = "KITTY_SCROLLBACK_DIR=${scrollbackDir}";
              ExecStart = "${scriptPkgs.kitty-scrollback-capture}/bin/kitty-scrollback-capture";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [ scrollbackDir ];
            };
          };
        };

        systemd.user.timers.sinnix-capture-kitty-scrollback = {
          Unit.Description = "Periodic trigger for kitty scrollback capture";
          Timer = {
            OnUnitActiveSec = "${toString cfg.intervalMinutes}min";
            OnStartupSec = "2min";
            Persistent = true;
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
