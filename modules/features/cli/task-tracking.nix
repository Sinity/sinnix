{ mkFeatureModule, config, ... }@args:
mkFeatureModule {
  path = [
    "cli"
    "task-tracking"
  ];
  description = "Taskwarrior and Timewarrior task tracking";
  meta.dotfiles = {
    configFile = {
      "task/taskrc" = {
        source = "taskwarrior/taskrc";
        force = true;
      };
      "timewarrior/timewarrior.cfg" = {
        source = "timewarrior/timewarrior.cfg";
        force = true;
      };
      "timewarrior/extensions/balance.py" = {
        source = "timewarrior/extensions/balance.py";
        force = true;
      };
      "timewarrior/extensions/on-modify.timewarrior" = {
        source = "timewarrior/extensions/on-modify.timewarrior";
        force = true;
      };
      "timewarrior/extensions/productivity.py" = {
        source = "timewarrior/extensions/productivity.py";
        force = true;
      };
    };
    dataFile = {
      "task/hooks/on-add-inbox.py" = "taskwarrior/hooks/on-add-inbox.py";
      "task/hooks/on-modify-review.py" = "taskwarrior/hooks/on-modify-review.py";
    };
  };
  configFn =
    {
      config,
      lib,
      user,
      ...
    }:
    let
      dotsRoot = "${config.sinnix.paths.projectRoot}/dots";
    in
    {
      home-manager.users.${user} =
        { config, ... }:
        {
          xdg.dataHome = lib.mkDefault "${config.home.homeDirectory}/.local/share";

          # Source shell integration
          programs.zsh.initContent = lib.mkAfter ''
            # Taskwarrior shell aliases and helpers
            [ -f "${dotsRoot}/taskwarrior/shell-aliases.sh" ] && source "${dotsRoot}/taskwarrior/shell-aliases.sh"
            # Agent helpers only loaded when AGENT_NAME is set (Claude/Codex sessions)
            [ -n "''${AGENT_NAME:-}" ] && [ -f "${dotsRoot}/taskwarrior/agent-helpers.sh" ] && source "${dotsRoot}/taskwarrior/agent-helpers.sh"
          '';
        };
    };
} args
