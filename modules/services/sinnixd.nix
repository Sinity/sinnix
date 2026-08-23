{
  mkServiceModule,
  config,
  helpers,
  lib,
  pkgs,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  projectRoot = config.sinnix.paths.projectRoot;
in
mkServiceModule {
  name = "sinnixd";
  description = "Local Sinnix runtime daemon for agentctl and MCP frontends";
  extraOptions.agentRunner = lib.mkOption {
    type = lib.types.str;
    default = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-orchestration/scripts/run_agent_prompt.sh";
    description = "Native attested-agent execution backend; Sinnixd retains systemd lifecycle authority.";
  };
  surface = {
    unit = "sinnixd.service";
    manager = "user";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { cfg, ... }:
    {
      environment.systemPackages = [ scriptPkgs.sinnixd ];
      sinnix.persistence.home.directories = [ ".local/state/sinnixd" ];

      home-manager.users.${userName}.systemd.user.services.sinnixd = {
        Unit = {
          Description = "Sinnix local runtime daemon";
          After = [ "graphical-session.target" ];
        };
        Service =
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnixd.service";
          })
          // {
            Type = "simple";
            ExecStart = "${scriptPkgs.sinnixd}/bin/sinnixd --socket %t/sinnixd.sock --state-dir %S/sinnixd --project-root ${projectRoot} --native-runner ${lib.escapeShellArg cfg.agentRunner}";
            Restart = "on-failure";
            RestartSec = "2s";
            UMask = "0077";
          };
        Install.WantedBy = [ "default.target" ];
      };
    };
} args
