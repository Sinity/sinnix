{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
let
  inherit (lib) mkEnableOption mkIf;
  cfg = config.services.polylogue-watch;
  polyloguePkg =
    pkgs.polylogue or inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.polylogue;
in
{
  options.services.polylogue-watch.enable = mkEnableOption "Polylogue watch services";

  config = mkIf cfg.enable (
    let
      chatlogRoot = "/realm/data/chatlog";
      inboxRoot = chatlogRoot + "/inbox";
      archiveRoot = chatlogRoot + "/markdown";
      configRoot = chatlogRoot + "/config";
      stateRoot = chatlogRoot + "/state";
      tmpRules = map (dir: "d ${dir} 0755 root root - -") [
        chatlogRoot
        inboxRoot
        archiveRoot
        configRoot
        stateRoot
      ];
      configJson = builtins.toJSON {
        paths = {
          input_root = inboxRoot;
          output_root = archiveRoot;
        };
        ui = {
          collapse_threshold = 25;
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
      };
      configPath = configRoot + "/config.json";
      envVars = {
        XDG_CONFIG_HOME = configRoot;
        XDG_DATA_HOME = chatlogRoot;
        XDG_STATE_HOME = stateRoot;
        POLYLOGUE_FORCE_PLAIN = "1";
        POLYLOGUE_CONFIG = configPath;
      };
      mkService = name: args: {
        description = "Polylogue ${name} watcher";
        wantedBy = [ "multi-user.target" ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = lib.escapeShellArgs ([ "${polyloguePkg}/bin/polylogue" ] ++ args);
          Restart = "always";
          WorkingDirectory = chatlogRoot;
          Environment = lib.mapAttrsToList (n: v: "${n}=${v}") envVars;
        };
      };
      services = {
        "polylogue-watch-codex" = mkService "codex" [
          "sync"
          "codex"
          "--watch"
          "--out"
          (archiveRoot + "/codex")
        ];
        "polylogue-watch-claude-code" = mkService "claude-code" [
          "sync"
          "claude-code"
          "--watch"
          "--out"
          (archiveRoot + "/claude-code")
        ];
        "polylogue-watch-chatgpt" = mkService "chatgpt" [
          "sync"
          "chatgpt"
          "--watch"
          "--base-dir"
          inboxRoot
          "--out"
          (archiveRoot + "/chatgpt")
        ];
        "polylogue-watch-claude" = mkService "claude" [
          "sync"
          "claude"
          "--watch"
          "--base-dir"
          inboxRoot
          "--out"
          (archiveRoot + "/claude")
        ];
      };
      writeConfig = ''
                install -d -m 0755 ${configRoot}
                cat > ${configPath} <<'EOFCFG'
        ${configJson}
        EOFCFG
      '';
    in
    {
      system.activationScripts.polylogue-config = writeConfig;
      systemd.tmpfiles.rules = tmpRules;
      systemd.services = services;
    }
  );
}
