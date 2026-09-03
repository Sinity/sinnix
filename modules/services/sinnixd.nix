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
  name = "sinnixd";
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
        throw "sinnix.services.sinnixd.projectRoots must contain unique absolute project roots";
    description = "Explicit project roots whose .agentctl/project.toml descriptors agentctl reads; no parent directory is scanned.";
  };
  extraOptions.refill = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule {
        options = {
          limit = lib.mkOption {
            type = lib.types.ints.positive;
            default = 1;
            description = "Lanes started per firing.";
          };
          onCalendar = lib.mkOption {
            type = lib.types.str;
            default = "hourly";
            description = "OnCalendar expression of the refill timer.";
          };
        };
      }
    );
    default = { };
    description = "Opt-in refill timers by project id: each firing runs `agentctl refill <project> --limit N`.";
  };
  extraOptions.agentRunner = lib.mkOption {
    type = lib.types.str;
    default = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh";
    description = "The backend adapter `agentctl lane start` queues; it turns a prompt file into one backend invocation.";
  };
  # No runtime surface: the job plane is pueued (declared by the CLI feature)
  # inside the sinnixd slice hierarchy, and the units here are two timers.
  configFn =
    { cfg, ... }:
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnixd-backpressure";
          description = "Freeze the job queue while the host is stalled";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          execStart = "${scriptPkgs.sinnixd}/bin/sinnixd-backpressure --event-spool ${lib.escapeShellArg eventSpool}";
          serviceConfig = {
            TimeoutStartSec = "30s";
            ReadWritePaths = [ (builtins.dirOf eventSpool) ];
          };
          timer = {
            # Full-stall averages are 60-second means, so sampling faster reads
            # the same number twice. One group is frozen or thawed per tick, so
            # freezing agent, normal and bulk takes three minutes: the queue
            # backs off in steps rather than stopping the host at once.
            onUnitActiveSec = 60;
            onBootSec = 60;
            description = "Freeze the job queue while the host is stalled";
          };
        }
      )
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnixd-schedule";
          description = "Reconcile the calendar timers declared by project descriptors";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          # Each declared `schedule` becomes one transient timer running
          # `agentctl job fire`; a changed or removed declaration is stopped.
          execStart = "${scriptPkgs.sinnixd}/bin/agentctl schedule apply";
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
      (lib.mkMerge (
        lib.mapAttrsToList (
          project: refill:
          lib.sinnix.mkScheduledJob
            {
              inherit config;
              unitName = "sinnixd-refill-${project}";
              description = "Start lanes for ready ${project} beads";
            }
            {
              manager = "user";
              resourceClass = "background-maintenance";
              execStart = "${scriptPkgs.sinnixd}/bin/agentctl refill ${lib.escapeShellArg project} --limit ${toString refill.limit}";
              serviceConfig = {
                TimeoutStartSec = "10min";
              };
              timer = {
                onCalendar = refill.onCalendar;
                description = "Start lanes for ready ${project} beads";
              };
            }
        ) cfg.refill
      ))
      {
        environment.etc."sinnix/agentctl.json".text = builtins.toJSON {
          project_roots = cfg.projectRoots;
          agent_runner = cfg.agentRunner;
          event_spool = eventSpool;
          agentctl = "${scriptPkgs.sinnixd}/bin/agentctl";
        };
        # Queued commands and the timers run with the system PATH, not an
        # interactive profile, so the tools agentctl shells out to must be
        # system packages.
        environment.systemPackages = [
          scriptPkgs.sinnixd
          scriptPkgs.polylogue-cli
          pkgs.worktrunk
          pkgs.pueue
          pkgs.gh
        ];
        systemd.tmpfiles.rules = [ "d ${taskStateRoot} 0700 ${userName} users -" ];
        # Launch inputs, bounded logs and typed results of queued jobs.
        sinnix.persistence.home.directories = [ ".local/state/sinnixd" ];
      }
    ];
} args
