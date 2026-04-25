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
      default = "1h";
      description = "How often to run durable polylogue archive catch-up (systemd timer format).";
    };

    browserCapture = {
      enable = lib.mkEnableOption "Polylogue local browser-capture receiver" // {
        default = true;
      };

      host = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "Host for the local-only browser-capture receiver.";
      };

      port = lib.mkOption {
        type = lib.types.port;
        default = 8765;
        description = "Port for the local-only browser-capture receiver.";
      };
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
        Unit = {
          Description = "Polylogue durable archive catch-up";
          # This oneshot can run for many minutes. Do not let Home Manager's
          # unit switcher start/restart it inline during a rebuild; the timer
          # and explicit operator starts own execution.
          X-SwitchMethod = "keep-old";
        };
        Service = {
          Type = "oneshot";
          ExecStart = "${pkgs.polylogue}/bin/polylogue --plain run acquire parse materialize render index";
          # Background priority — ingestion shouldn't compete with interactive work
          Nice = 19;
          IOSchedulingClass = "idle";
          # Bound runtime: prevents hangs if Drive API stalls while still
          # allowing render/site/index catch-up on active days.
          TimeoutStartSec = "30min";
          # Memory limits: polylogue hit 16GB RSS ingesting conversations,
          # pushing everything to swap. MemoryHigh triggers aggressive reclaim;
          # MemoryMax kills if it still grows (prevents system-wide I/O storm).
          MemoryHigh = "2G";
          MemoryMax = "4G";
        };
      };

      systemd.user.services.polylogue-browser-capture = lib.mkIf cfg.browserCapture.enable {
        Unit = {
          Description = "Polylogue local browser-capture receiver";
          After = [ "default.target" ];
        };
        Service = {
          ExecStart = "${pkgs.polylogue}/bin/polylogue --plain browser-capture serve --host ${cfg.browserCapture.host} --port ${toString cfg.browserCapture.port}";
          Restart = "on-failure";
          RestartSec = "5s";
          Nice = 10;
          IOSchedulingClass = "idle";
          MemoryHigh = "256M";
          MemoryMax = "512M";
        };
        Install.WantedBy = [ "default.target" ];
      };

      systemd.user.timers.polylogue-run = {
        Unit.Description = "Polylogue periodic archive catch-up";
        Timer = {
          OnStartupSec = "2min";
          OnUnitInactiveSec = cfg.interval;
          # Catch up on missed runs (laptop was asleep)
          Persistent = true;
          Unit = "polylogue-run.service";
        };
        Install.WantedBy = [ "timers.target" ];
      };
    };
  };
}
