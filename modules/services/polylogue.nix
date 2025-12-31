{ config, lib, pkgs, ... }:
let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.sinnix.services.polylogue;
  user = config.sinnix.user.name;
  userGroup = config.users.users.${user}.group or user;

  chatlogRoot = "${config.sinnix.paths.dataRoot}/chatlog";
  inboxRoot = "${chatlogRoot}/inbox";
  archiveRoot = "${chatlogRoot}/archive";
  configRoot = "${chatlogRoot}/config";
  stateRoot = "${chatlogRoot}/state";
  stateAppRoot = "${stateRoot}/polylogue";
  configPath = "${configRoot}/config.json";

  polylogueBin = "${pkgs.polylogue}/bin/polylogue";

  envVars = {
    XDG_CONFIG_HOME = configRoot;
    XDG_DATA_HOME = chatlogRoot;
    XDG_STATE_HOME = stateRoot;
    POLYLOGUE_CONFIG = configPath;
    POLYLOGUE_FORCE_PLAIN = "1";
    POLYLOGUE_CREDENTIAL_PATH = "${configRoot}/credentials.json";
    POLYLOGUE_TOKEN_PATH = "${configRoot}/token.json";
    POLYLOGUE_DRIVE_RETRIES = toString cfg.drive.retries;
    POLYLOGUE_DRIVE_RETRY_BASE = toString cfg.drive.retryBase;
  };

  dirs =
    [
      chatlogRoot
      configRoot
      stateRoot
      stateAppRoot
      inboxRoot
      archiveRoot
    ];

  tmpfilesRules = map (dir: "d ${dir} 0755 ${user} ${userGroup} - -") dirs;

  configJson = builtins.toJSON {
    version = 2;
    archive_root = archiveRoot;
    sources = [
      {
        name = "inbox";
        path = inboxRoot;
      }
      {
        name = "gemini";
        folder = "Google AI Studio";
      }
    ];
  };

  runArgs = [ "--plain" "run" ];
in
{
  options.sinnix.services.polylogue = {
    enable = mkEnableOption "Polylogue ingestion pipeline";
    drive = {
      retries = mkOption {
        type = types.int;
        default = 3;
        description = "Drive retry attempts for sync requests.";
      };
      retryBase = mkOption {
        type = types.float;
        default = 0.5;
        description = "Base delay (seconds) for Drive retry backoff.";
      };
    };
  };

  config = mkIf cfg.enable {
    system.activationScripts.polylogueConfig = ''
      ${lib.concatStringsSep "\n" (map (dir: "install -d -m 0755 -o ${user} -g ${userGroup} ${lib.escapeShellArg dir}") dirs)}
      cat > ${configPath} <<'EOF'
${configJson}
EOF
      chown ${user}:${userGroup} ${configPath}
      if [ -d ${lib.escapeShellArg stateAppRoot} ]; then
        chown -R ${user}:${userGroup} ${lib.escapeShellArg stateAppRoot}
      fi
    '';

    systemd.tmpfiles.rules = tmpfilesRules;

    systemd.services.polylogue-run = {
      description = "Polylogue ingest/render/index";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      unitConfig.RequiresMountsFor = [ chatlogRoot ];
      environment = envVars;
      serviceConfig = {
        Type = "oneshot";
        User = user;
        WorkingDirectory = chatlogRoot;
        ExecStart = lib.escapeShellArgs ([ polylogueBin ] ++ runArgs);
      };
    };

    systemd.timers.polylogue-run = {
      description = "Schedule Polylogue runs";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnStartupSec = "2min";
        OnUnitActiveSec = "15min";
        Unit = "polylogue-run.service";
      };
    };

    home-manager.users.${user}.home.sessionVariables = {
      POLYLOGUE_CONFIG = configPath;
      POLYLOGUE_CREDENTIAL_PATH = "${configRoot}/credentials.json";
      POLYLOGUE_TOKEN_PATH = "${configRoot}/token.json";
      POLYLOGUE_DRIVE_RETRIES = toString cfg.drive.retries;
      POLYLOGUE_DRIVE_RETRY_BASE = toString cfg.drive.retryBase;
    };

    environment.systemPackages = lib.mkAfter [ pkgs.polylogue ];
  };
}
