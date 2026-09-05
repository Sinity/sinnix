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
  eventSpool = "${config.sinnix.paths.stateRoot}/agentctl/events.jsonl";
in
mkServiceModule {
  name = "agentctl";
  description = "agentctl: jobs over pueue, lanes over worktrunk, gh and bd, and their timers";
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
        throw "sinnix.services.agentctl.projectRoots must contain unique absolute project roots";
    description = "Explicit project roots whose .agentctl/project.toml descriptors agentctl reads; no parent directory is scanned.";
  };
  extraOptions.agentRunner = lib.mkOption {
    type = lib.types.str;
    default = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh";
    description = "The backend adapter agentctl queues for batch workers and reviewers; it turns a prompt file into one backend invocation.";
  };
  # No runtime surface: the job plane is pueued (declared by the CLI feature)
  # inside the agentctl slice hierarchy, and the unit here is one timer.
  configFn =
    { cfg, ... }:
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-backpressure";
          description = "Freeze the job queue while the host is stalled";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          # The pass pauses and resumes pueue groups through the pueue client.
          path = [ pkgs.pueue ];
          execStart = "${scriptPkgs.agentctl}/bin/agentctl backpressure tick";
          serviceConfig = {
            TimeoutStartSec = "30s";
            ReadWritePaths = [ (builtins.dirOf eventSpool) ];
          };
          timer = {
            # Full-stall averages are 60-second means, so sampling faster reads
            # the same number twice. One group is paused or resumed per tick,
            # with the signal-specific order defined by `agentctl backpressure tick`.
            onUnitActiveSec = 60;
            onBootSec = 60;
            description = "Freeze the job queue while the host is stalled";
          };
        }
      )
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-schedule";
          description = "Reconcile the calendar timers declared by project descriptors";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          # Each declared `schedule` becomes one transient timer running
          # `agentctl job fire`; a changed or removed declaration is stopped.
          execStart = "${scriptPkgs.agentctl}/bin/agentctl schedule apply";
          serviceConfig = {
            TimeoutStartSec = "60s";
          };
          timer = {
            onUnitActiveSec = 900;
            onBootSec = 120;
            description = "Reconcile the calendar timers declared by project descriptors";
          };
        }
      )
      {
        environment.etc."sinnix/agentctl.json".text = builtins.toJSON {
          project_roots = cfg.projectRoots;
          agent_runner = cfg.agentRunner;
          event_spool = eventSpool;
          agentctl = "${scriptPkgs.agentctl}/bin/agentctl";
        };
        # Queued commands and the timers run with the system PATH, not an
        # interactive profile, so the tools agentctl shells out to must be
        # system packages.
        environment.systemPackages = [
          scriptPkgs.agentctl
          scriptPkgs.polylogue-cli
          pkgs.worktrunk
          pkgs.pueue
          pkgs.gh
        ];
        systemd.tmpfiles.rules = [ "d ${taskStateRoot} 0700 ${userName} users -" ];
        # Launch inputs, bounded logs and typed results of queued jobs.
        sinnix.persistence.home.directories = [ ".local/state/agentctl" ];
      }
    ];
} args
