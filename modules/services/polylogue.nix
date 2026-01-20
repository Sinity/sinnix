{
  config,
  lib,
  pkgs,
  ...
}:
let
  inherit (lib)
    mkEnableOption
    mkIf
    mkOption
    types
    ;
  cfg = config.sinnix.services.polylogue;
  user = config.sinnix.user.name;
  userGroup = config.users.users.${user}.group or user;

  userHome = config.users.users.${user}.home or "/home/${user}";
  xdgConfigHome = "${userHome}/.config";
  xdgStateHome = "${userHome}/.local/state";
  xdgDataHome = "${userHome}/.local/share";

  chatlogRoot = "${config.sinnix.paths.exportsRoot}/chatlog";
  inboxRoot = "${chatlogRoot}/raw/inbox";
  chatgptRoot = "${chatlogRoot}/raw/chatgpt";
  claudeRoot = "${chatlogRoot}/raw/claude";
  archiveRoot = "${chatlogRoot}/archive";
  renderRoot = "${chatlogRoot}/processed/markdown";
  codexRoot = "${userHome}/.codex/sessions";
  claudeCodeRoot = "${userHome}/.config/claude/projects";

  configRoot = "${xdgConfigHome}/polylogue";
  stateAppRoot = "${xdgStateHome}/polylogue";
  configPath = "${configRoot}/config.json";
  credentialsPath = "${configRoot}/credentials.json";
  tokenPath = "${stateAppRoot}/token.json";

  polylogueBin = "${pkgs.polylogue}/bin/polylogue";

  # Shared env vars used by both systemd services and user shell
  sharedEnvVars = {
    POLYLOGUE_CONFIG = configPath;
    POLYLOGUE_ARCHIVE_ROOT = archiveRoot;
    POLYLOGUE_RENDER_ROOT = renderRoot;
    POLYLOGUE_CREDENTIAL_PATH = credentialsPath;
    POLYLOGUE_TOKEN_PATH = tokenPath;
    POLYLOGUE_DRIVE_RETRIES = toString cfg.drive.retries;
    POLYLOGUE_DRIVE_RETRY_BASE = toString cfg.drive.retryBase;
    QDRANT_URL = cfg.qdrant.url;
  };

  # Systemd services need explicit XDG paths + FORCE_PLAIN
  envVars = sharedEnvVars // {
    XDG_CONFIG_HOME = xdgConfigHome;
    XDG_DATA_HOME = xdgDataHome;
    XDG_STATE_HOME = xdgStateHome;
    POLYLOGUE_FORCE_PLAIN = "1";
  };

  dataDirs = [
    chatlogRoot
    inboxRoot
    archiveRoot
    renderRoot
  ];

  sourceDirs = [
    codexRoot
    claudeCodeRoot
    chatgptRoot
    claudeRoot
  ];

  tmpfilesRules =
    (map (dir: "d ${dir} 0755 ${user} ${userGroup} - -") dataDirs)
    ++ (map (dir: "d ${dir} 0700 ${user} ${userGroup} - -") sourceDirs);

  configJson = builtins.toJSON {
    version = 2;
    archive_root = archiveRoot;
    render_root = renderRoot;
    sources = [
      {
        name = "inbox";
        path = inboxRoot;
      }
      {
        name = "codex";
        path = codexRoot;
      }
      {
        name = "claude-code";
        path = claudeCodeRoot;
      }
      {
        name = "chatgpt";
        path = chatgptRoot;
      }
      {
        name = "claude";
        path = claudeRoot;
      }

      {
        name = "gemini";
        folder = "Google AI Studio";
      }
    ];
  };

  runArgs = [
    "--plain"
    "run"
  ];
in
{
  options.sinnix.services.polylogue = {
    enable = mkEnableOption "Polylogue ingestion pipeline";
    server = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = "Enable Polylogue Semantic API server.";
      };
      port = mkOption {
        type = types.int;
        default = 8000;
        description = "Port to bind.";
      };
    };
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
    qdrant = {
      url = mkOption {
        type = types.str;
        default = "http://localhost:6333";
        description = "Qdrant server URL.";
      };
    };
  };

  config = mkIf cfg.enable {
    system.activationScripts.polylogueConfig = lib.stringAfter [ "etc" "users" "groups" ] ''
            ${lib.concatStringsSep "\n" (
              map (dir: "install -d -m 0755 -o ${user} -g ${userGroup} ${lib.escapeShellArg dir}") dataDirs
            )}
            install -d -m 0700 -o ${user} -g ${userGroup} ${lib.escapeShellArg configRoot}
            install -d -m 0700 -o ${user} -g ${userGroup} ${lib.escapeShellArg xdgStateHome}
            install -d -m 0700 -o ${user} -g ${userGroup} ${lib.escapeShellArg stateAppRoot}
            
            # Write config atomically
            cat > ${configPath}.tmp <<'EOF'
      ${configJson}
      EOF
            mv ${configPath}.tmp ${configPath}
            chown ${user}:${userGroup} ${configPath}
            chown -R ${user}:${userGroup} ${lib.escapeShellArg stateAppRoot}
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
        # Restart protection for oneshot
        Restart = "on-failure";
        RestartSec = 10;
        StartLimitBurst = 5;
        StartLimitIntervalSec = 60;
        # Hardening
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictRealtime = true;
        LockPersonality = true;
        ReadWritePaths = [ chatlogRoot stateAppRoot ];
      };
    };

    systemd.services.polylogue-serve = mkIf cfg.server.enable {
      description = "Polylogue Semantic API Server";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      unitConfig.RequiresMountsFor = [ chatlogRoot ];
      environment = envVars;
      serviceConfig = {
        Type = "simple";
        User = user;
        WorkingDirectory = chatlogRoot;
        ExecStart = "${polylogueBin} serve --host 127.0.0.1 --port ${toString cfg.server.port}";
        Restart = "on-failure";
        RestartSec = 5;
        # Hardening
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictRealtime = true;
        LockPersonality = true;
        ReadWritePaths = [ chatlogRoot stateAppRoot ];
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

    environment.sessionVariables = sharedEnvVars;

    environment.systemPackages = lib.mkAfter [ pkgs.polylogue ];
  };
}
