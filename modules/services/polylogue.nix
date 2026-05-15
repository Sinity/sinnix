# Polylogue - AI conversation archive
#
# Daemon ingestion of AI chat exports (ChatGPT, Claude, Claude Code,
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
    enable = lib.mkEnableOption "Polylogue daemon ingestion";

    daemon = {
      enable = lib.mkEnableOption "Polylogue long-running daemon (live watcher + browser capture)" // {
        default = true;
      };

      autoStart = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Start the Polylogue daemon automatically in the user session.";
      };

      host = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "Host for the daemon's local browser-capture receiver.";
      };

      port = lib.mkOption {
        type = lib.types.port;
        default = 8765;
        description = "Port for the daemon's local browser-capture receiver.";
      };

      browserCapture = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Run browser-capture inside the long-lived daemon.";
      };

      nice = lib.mkOption {
        type = lib.types.ints.between (-20) 19;
        default = 10;
        description = "Unix nice value for the long-running daemon.";
      };

      ioSchedulingClass = lib.mkOption {
        type = lib.types.enum [
          "idle"
          "best-effort"
          "realtime"
        ];
        default = "idle";
        description = "Linux I/O scheduling class for the long-running daemon.";
      };

      ioWeight = lib.mkOption {
        type = lib.types.ints.between 1 10000;
        default = 10;
        description = "Cgroup v2 I/O weight for the long-running daemon.";
      };

      memoryHigh = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = "8G";
        description = "Soft cgroup memory pressure threshold for the long-running daemon.";
      };

      memoryMax = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = "12G";
        description = "Hard cgroup memory limit for the long-running daemon.";
      };
    };

    browserCapture = {
      enable = lib.mkEnableOption "Polylogue local browser-capture receiver" // {
        default = false; # daemon handles this by default
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
        unit = "polylogued.service";
        type = "user";
        restartable = true;
      };
      description = "Service health metadata consumed by introspection/sentinel.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ pkgs.polylogue ];

    home-manager.users.${userName} = {
      systemd.user.services.polylogue-browser-capture = lib.mkIf cfg.browserCapture.enable {
        Unit = {
          Description = "Polylogue local browser-capture receiver";
          After = [ "default.target" ];
        };
        Service = {
          ExecStart = "${pkgs.polylogue}/bin/polylogued browser-capture serve --host ${cfg.browserCapture.host} --port ${toString cfg.browserCapture.port}";
          Restart = "on-failure";
          RestartSec = "5s";
        };
        Install.WantedBy = [ "default.target" ];
      };

      systemd.user.services.polylogued = lib.mkIf cfg.daemon.enable {
        Unit = {
          Description = "Polylogue daemon - live watcher and browser capture";
          After = [ "default.target" ];
        };
        Service = {
          ExecStart =
            "${pkgs.polylogue}/bin/polylogued run --host ${cfg.daemon.host} --port ${toString cfg.daemon.port}"
            + lib.optionalString (!cfg.daemon.browserCapture) " --no-browser-capture";
          Restart = "on-failure";
          RestartSec = "5s";
          Nice = cfg.daemon.nice;
          IOSchedulingClass = cfg.daemon.ioSchedulingClass;
          IOWeight = cfg.daemon.ioWeight;
        }
        // lib.optionalAttrs (cfg.daemon.memoryHigh != null) {
          MemoryHigh = cfg.daemon.memoryHigh;
        }
        // lib.optionalAttrs (cfg.daemon.memoryMax != null) {
          MemoryMax = cfg.daemon.memoryMax;
        };
        Install.WantedBy = lib.optionals cfg.daemon.autoStart [ "default.target" ];
      };
    };
  };
}
