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
  runPressureGate = pkgs.writeShellScript "polylogue-run-pressure-gate" ''
    set -eu

    threshold="5.0"
    avg="$(
      ${pkgs.gawk}/bin/awk '
        /^full / {
          for (i = 1; i <= NF; i++) {
            if ($i ~ /^avg10=/) {
              sub(/^avg10=/, "", $i)
              print $i
              exit
            }
          }
        }
      ' /proc/pressure/io
    )"

    if ${pkgs.gawk}/bin/awk -v avg="$avg" -v threshold="$threshold" 'BEGIN { exit !(avg < threshold) }'; then
      exit 0
    fi

    echo "polylogue-run: skipped because io.full avg10=''${avg}% >= ''${threshold}%" >&2
    exit 1
  '';
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
          ExecCondition = "${runPressureGate}";
          ExecStart = "${pkgs.polylogue}/bin/polylogue --plain run acquire parse materialize render index";
          # Background priority — ingestion shouldn't compete with interactive work
          Nice = 19;
          IOSchedulingClass = "idle";
          IOWeight = 1;
          IOReadBandwidthMax = [
            "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 60M"
            "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 60M"
          ];
          IOWriteBandwidthMax = [
            "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea 60M"
            "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 60M"
          ];
          # Bound runtime: prevents hangs if Drive API stalls while still
          # allowing render/site/index catch-up on active days.
          TimeoutStartSec = "30min";
          # Memory limits are runaway guardrails, not a normal operating
          # budget. Polylogue has previously grown into swap during catch-up;
          # leave headroom for legitimate archive work while preventing a
          # single run from consuming the whole workstation.
          MemoryHigh = "8G";
          MemoryMax = "16G";
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
          OnStartupSec = "30min";
          OnUnitInactiveSec = cfg.interval;
          Persistent = false;
          Unit = "polylogue-run.service";
        };
        Install.WantedBy = [ "timers.target" ];
      };
    };
  };
}
