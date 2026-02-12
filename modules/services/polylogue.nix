# Polylogue - AI conversation archive service
#
# Provides scheduled ingestion of AI chat exports from multiple sources:
# - ChatGPT/Claude exports via inbox symlinks
# - Claude Code sessions from ~/.claude/projects
# - Codex sessions from ~/.codex/sessions
# - Gemini via Google Drive integration
#
# Uses user-level systemd timer for periodic runs, matching the XDG-based
# storage layout the user already has configured.
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
      description = "How often to run polylogue ingestion (systemd timer format)";
    };

    onStartupDelay = lib.mkOption {
      type = lib.types.str;
      default = "2min";
      description = "Delay before first run after boot";
    };
  };

  config = lib.mkIf cfg.enable {
    # Ensure polylogue package is available
    environment.systemPackages = [ pkgs.polylogue ];

    # User-level systemd service and timer via Home Manager
    home-manager.users.${userName} = {
      systemd.user.services.polylogue-run = {
        Unit = {
          Description = "Polylogue ingest/render/index";
          After = [ "network-online.target" ];
          Wants = [ "network-online.target" ];
        };
        Service = {
          Type = "oneshot";
          ExecStart = "${pkgs.polylogue}/bin/polylogue --plain run";
          Environment = [
            "POLYLOGUE_FORCE_PLAIN=1"
          ];
        };
      };

      systemd.user.timers.polylogue-run = {
        Unit = {
          Description = "Schedule Polylogue runs";
        };
        Timer = {
          OnStartupSec = cfg.onStartupDelay;
          OnUnitActiveSec = cfg.interval;
          Unit = "polylogue-run.service";
        };
        Install = {
          WantedBy = [ "timers.target" ];
        };
      };
    };
  };
}
