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
  taskStateRoot = "${config.sinnix.paths.stateRoot}/tasks";
in
mkServiceModule {
  name = "sinnixd";
  description = "Local Sinnix runtime daemon for agentctl and MCP frontends";
  extraOptions.projectRoots = lib.mkOption {
    type = lib.types.nonEmptyListOf lib.types.str;
    default = map (project: project.path) (lib.attrValues config.sinnix.projects.entries);
    apply =
      roots:
      if
        lib.all (root: lib.hasPrefix "/" root) roots && lib.length roots == lib.length (lib.unique roots)
      then
        roots
      else
        throw "sinnix.services.sinnixd.projectRoots must contain unique absolute project roots";
    description = "Explicit project roots whose .agentctl/project.toml descriptors Sinnixd loads; no parent directory is scanned.";
  };
  extraOptions.agentRunner = lib.mkOption {
    type = lib.types.str;
    default = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh";
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
    let
      projectRootArgs = lib.concatMapStringsSep " " (
        root: "--project-root ${lib.escapeShellArg root}"
      ) cfg.projectRoots;
    in
    {
      # Declared owner adapters run under env -i with the daemon's system PATH.
      # Keep their fixed packaged entrypoints in that PATH rather than relying
      # on an interactive Home Manager profile.
      environment.systemPackages = [
        scriptPkgs.sinnixd
        scriptPkgs.polylogue-cli
        # The worktree and queue planes the daemon shells out to. They must be
        # system packages: a Home Manager profile is not on the env -i PATH.
        pkgs.worktrunk
        pkgs.pueue
      ];
      systemd.tmpfiles.rules = [ "d ${taskStateRoot} 0700 ${userName} users -" ];
      sinnix.persistence.home.directories = [ ".local/state/sinnixd" ];
      sinnix.runtime.surfaces.sinnixd-jobs = {
        unit = "sinnixd-job-.service";
        manager = "user";
        kind = "service";
        dynamic = true;
        resourceClass = "managed-runtime-work";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Transient work yields to interactive slices and is killed as a cgroup under sustained host exhaustion.";
          processMatchers = [ "sinnixd-job-" ];
        };
        captures = [
          {
            name = "sinnixd-job-records";
            path = "/home/${userName}/.local/state/sinnixd/jobs";
            eventDriven = true;
          }
        ];
      };

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
            ExecStart = "${scriptPkgs.sinnixd}/bin/sinnixd --socket %t/sinnixd.sock --state-dir %S/sinnixd ${projectRootArgs} --native-runner ${lib.escapeShellArg cfg.agentRunner}";
            Restart = "on-failure";
            RestartSec = "2s";
            UMask = "0077";
            Environment = [ "SINNIXD_TASK_STATE_ROOT=${taskStateRoot}" ];
          };
        Install.WantedBy = [ "default.target" ];
      };
    };
} args
