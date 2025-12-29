{ config, lib, pkgs, ... }:
let
  inherit (lib) mkEnableOption mkIf mkMerge;
  cfg = config.sinnix.services.polylogue-watch;
  user = config.sinnix.user.name;
  userGroup = config.users.users.${user}.group or user;

  chatlogRoot = "/realm/data/chatlog";
  inboxRoot = "${chatlogRoot}/inbox";
  archiveRoot = "${chatlogRoot}/markdown";
  configRoot = "${chatlogRoot}/config";
  stateRoot = "${chatlogRoot}/state";
  stateAppRoot = "${stateRoot}/polylogue";

  polylogueBin = "${pkgs.polylogue}/bin/polylogue";
  tessdataDir = "${pkgs.tesseract}/share/tessdata";

  envVars = {
    XDG_CONFIG_HOME = configRoot;
    XDG_DATA_HOME = chatlogRoot;
    XDG_STATE_HOME = stateRoot;
    POLYLOGUE_CONFIG = "${configRoot}/config.json";
    POLYLOGUE_FORCE_PLAIN = "1";
    POLYLOGUE_DECLARATIVE = "1";
    POLYLOGUE_CREDENTIAL_PATH = "${configRoot}/credentials.json";
    POLYLOGUE_TOKEN_PATH = "${configRoot}/token.json";
    TESSDATA_PREFIX = tessdataDir;
  };

  providerPaths = {
    gemini = "${archiveRoot}/gemini";
    codex = "${archiveRoot}/codex";
    claudeCode = "${archiveRoot}/claude-code";
    chatgpt = "${archiveRoot}/chatgpt";
    claude = "${archiveRoot}/claude";
  };

  inboxPaths = {
    chatgpt = "${inboxRoot}/chatgpt";
    claude = "${inboxRoot}/claude";
  };

  dirs =
    [
      chatlogRoot
      configRoot
      stateRoot
      stateAppRoot
      inboxRoot
      archiveRoot
    ]
    ++ lib.attrValues providerPaths
    ++ lib.attrValues inboxPaths;

  tmpfilesRules = map (dir: "d ${dir} 0755 ${user} ${userGroup} - -") dirs;

  configJson = builtins.toJSON {
    paths = {
      input_root = inboxRoot;
      output_root = archiveRoot;
    };
    exports = {
      chatgpt = inboxPaths.chatgpt;
      claude = inboxPaths.claude;
    };
    ui = {
      collapse_threshold = 25;
      html = true;
      theme = "dark";
    };
    index = {
      backend = "sqlite";
      qdrant = {
        url = null;
        api_key = null;
        collection = "polylogue";
        vector_size = null;
      };
    };
    drive = {
      credentials_path = "${configRoot}/credentials.json";
      token_path = "${configRoot}/token.json";
      retries = 3;
      retry_base = 0.5;
    };
  };

  helperPackages = with pkgs; [
    polylogue
    skim
    bat
    glow
    fd
    ripgrep
    jq
    tesseract
  ];

  mkWatchService = name: args: {
    systemd.services."polylogue-watch-${name}" = {
      description = "Polylogue ${name} watcher";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      path = helperPackages;
      environment = envVars;
      serviceConfig = {
        Type = "simple";
        User = user;
        WorkingDirectory = chatlogRoot;
        ExecStart = lib.escapeShellArgs ([ polylogueBin ] ++ args);
        Restart = "always";
        RestartSec = 5;
      };
    };
  };

  watchServices = mkMerge [
    (mkWatchService "codex" [ "sync" "codex" "--watch" "--out" providerPaths.codex ])
    (mkWatchService "claude-code" [ "sync" "claude-code" "--watch" "--out" providerPaths.claudeCode ])
    (mkWatchService "chatgpt" [ "sync" "chatgpt" "--watch" "--base-dir" inboxPaths.chatgpt "--out" providerPaths.chatgpt ])
    (mkWatchService "claude" [ "sync" "claude" "--watch" "--base-dir" inboxPaths.claude "--out" providerPaths.claude ])
  ];
in
{
  options.sinnix.services.polylogue-watch.enable = mkEnableOption "Polylogue watch services";

  config = mkIf cfg.enable (lib.mkMerge [
    {
      system.activationScripts.polylogueConfig = ''
      ${lib.concatStringsSep "\n" (map (dir: "install -d -m 0755 -o ${user} -g ${userGroup} ${lib.escapeShellArg dir}") dirs)}
      cat > ${configRoot}/config.json <<'EOF'
${configJson}
EOF
      chown ${user}:${userGroup} ${configRoot}/config.json
      if [ -d ${lib.escapeShellArg stateAppRoot} ]; then
        chown -R ${user}:${userGroup} ${lib.escapeShellArg stateAppRoot}
      fi
    '';

      systemd.tmpfiles.rules = tmpfilesRules;

      home-manager.users.${user}.home.sessionVariables = {
        POLYLOGUE_CONFIG = "${configRoot}/config.json";
        POLYLOGUE_DECLARATIVE = "1";
        POLYLOGUE_CREDENTIAL_PATH = "${configRoot}/credentials.json";
        POLYLOGUE_TOKEN_PATH = "${configRoot}/token.json";
      };

      environment.systemPackages = lib.mkAfter [ pkgs.polylogue ];
    }
    watchServices
  ]);
}
