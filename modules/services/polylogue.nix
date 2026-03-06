# Polylogue - AI conversation archive
#
# Periodic ingestion of AI chat exports (ChatGPT, Claude, Claude Code,
# Codex, Gemini). Sources are auto-discovered from XDG paths; no
# configuration needed beyond enabling the service.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.services.polylogue;
  userName = config.sinnix.user.name;
in
{
  options.sinnix.services.polylogue = {
    enable = lib.mkEnableOption "Polylogue scheduled ingestion";

    interval = lib.mkOption {
      type = lib.types.str;
      default = "15min";
      description = "How often to run polylogue ingestion (systemd timer format).";
    };

    health = lib.mkOption {
      type = lib.types.nullOr (
        lib.types.submodule {
          options = {
            unit = lib.mkOption {
              type = lib.types.str;
            };
            type = lib.mkOption {
              type = lib.types.enum [
                "service"
                "timer"
                "user"
              ];
            };
            restartable = lib.mkOption {
              type = lib.types.bool;
            };
          };
        }
      );
      default = {
        unit = "polylogue-run.timer";
        type = "timer";
        restartable = false;
      };
      description = "Service health metadata consumed by introspection/sentinel.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.polylogue ];

    home-manager.users.${userName} = {
      systemd.user.services.polylogue-run = {
        Unit.Description = "Polylogue ingest/render/index";
        Service = {
          Type = "oneshot";
          ExecStart = "${pkgs.polylogue}/bin/polylogue --plain run";
          # Background priority — ingestion shouldn't compete with interactive work
          Nice = 19;
          IOSchedulingClass = "idle";
          # Bound runtime: prevents hangs if Drive API stalls
          TimeoutStartSec = "10min";
          # Memory limits: polylogue hit 16GB RSS ingesting conversations,
          # pushing everything to swap. MemoryHigh triggers aggressive reclaim;
          # MemoryMax kills if it still grows (prevents system-wide I/O storm).
          MemoryHigh = "2G";
          MemoryMax = "4G";
        };
      };

      systemd.user.timers.polylogue-run = {
        Unit.Description = "Polylogue periodic sync";
        Timer = {
          OnStartupSec = "2min";
          OnUnitActiveSec = cfg.interval;
          # Catch up on missed runs (laptop was asleep)
          Persistent = true;
          Unit = "polylogue-run.service";
        };
        Install.WantedBy = [ "timers.target" ];
      };
    };
  };
}
