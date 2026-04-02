{ mkFeatureModule, config, ... }@args:
mkFeatureModule {
  path = [
    "cli"
    "task-tracking"
  ];
  description = "Taskwarrior and Timewarrior task tracking";
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

          xdg.configFile = {
            # Link taskwarrior configuration
            "task/taskrc".source = config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/taskwarrior/taskrc";

            # Link timewarrior configuration
            "timewarrior/timewarrior.cfg".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/timewarrior/timewarrior.cfg";

            "timewarrior/extensions/balance.py".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/timewarrior/extensions/balance.py";
            "timewarrior/extensions/on-modify.timewarrior".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/timewarrior/extensions/on-modify.timewarrior";
            "timewarrior/extensions/productivity.py".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/timewarrior/extensions/productivity.py";
          };

          # Link taskwarrior hooks
          xdg.dataFile = {
            "task/hooks/on-add-inbox.py".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/taskwarrior/hooks/on-add-inbox.py";
            "task/hooks/on-modify-review.py".source =
              config.lib.file.mkOutOfStoreSymlink "${dotsRoot}/taskwarrior/hooks/on-modify-review.py";
          };

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
