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
  taskAuthorityParents = lib.unique (
    lib.filter (path: path != taskStateRoot) (
      lib.mapAttrsToList (
        _: project:
        if project.taskAuthority == null then
          taskStateRoot
        else
          builtins.dirOf project.taskAuthority.workspace
      ) config.sinnix.projects.entries
    )
  );
  eventSpool = "${config.sinnix.paths.stateRoot}/agentctl/events.jsonl";
  # One landing slot per project: `agentctl batch land` serializes through
  # <project>-land.
  landPools = lib.mapAttrs' (id: _: lib.nameValuePair "${id}-land" { parallel = 1; }) (
    lib.filterAttrs (_: project: project.agentctl) config.sinnix.projects.entries
  );
in
mkServiceModule {
  name = "agentctl";
  defaultOnDesktop = true;
  description = "agentctl: jobs over pueue, lanes over worktrunk, gh and bd, and their timers";
  extraOptions.projectRoots = lib.mkOption {
    type = lib.types.nonEmptyListOf lib.types.str;
    default = map (project: project.path) (
      lib.attrValues (lib.filterAttrs (_: project: project.agentctl) config.sinnix.projects.entries)
    );
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
  extraOptions.pools = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule {
        options = {
          parallel = lib.mkOption {
            type = lib.types.ints.positive;
            description = "How many tasks this pueue group admits at once.";
          };
        };
      }
    );
    default = {
      agent.parallel = 12;
      # The agents a landing owns (integration, review): a pool of their own so
      # a paused `agent` pool holds back new workers without stalling landings.
      land-agent.parallel = 2;
      pytest.parallel = 2;
      # Bounded selections stay admissible beside a wave: a worker runs its own
      # focused tests here while its own task occupies the agent pool.
      pytest-quick.parallel = 2;
      bulk.parallel = 2;
      normal.parallel = 2;
      interactive.parallel = 4;
    }
    // landPools
    // {
      # Polylogue lands several runs at once; each run still lands one at a time.
      polylogue-land.parallel = 3;
    };
    description = "Each pueue group's parallelism, which `agentctl pools apply` writes into the running daemon.";
  };
  extraOptions.workerContract = lib.mkOption {
    type = lib.types.str;
    default = "${config.sinnix.paths.dotsRoot}/_ai/skills/orchestrate/references/worker-contract.md";
    description = "The worker contract compiled into a worker prompt when a project descriptor names no template of its own.";
  };
  # No runtime surface: the job plane is pueued (declared by the CLI feature)
  # inside the agentctl slice hierarchy; the units here drive it.
  configFn =
    { cfg, ... }:
    let
      configFile = pkgs.writeText "agentctl.json" (
        builtins.toJSON {
          project_roots = cfg.projectRoots;
          private_project_catalog = config.sinnix.projects.privateCatalogFile;
          agent_runner = cfg.agentRunner;
          worker_contract = cfg.workerContract;
          event_spool = eventSpool;
          agentctl = "${scriptPkgs.agentctl}/bin/agentctl";
          pools = lib.mapAttrs (_name: pool: pool.parallel) cfg.pools;
        }
      );
    in
    lib.mkMerge [
      {
        sinnix.runtime.dataStores = {
          agentctl-events = {
            path = eventSpool;
            class = "canonical";
          };
          agentctl-state = {
            path = "${config.sinnix.paths.stateRoot}/agentctl";
            class = "canonical";
          };
          task-authorities = {
            path = taskStateRoot;
            class = "canonical";
          };
        };
      }
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-backpressure";
          description = "Reconcile queue admission against host stall";
        }
        {
          manager = "user";
          resourceClass = "background";
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
            description = "Reconcile queue admission against host stall";
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
          resourceClass = "background";
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
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-pools";
          description = "Apply the declared parallelism of every pueue group";
        }
        {
          manager = "user";
          resourceClass = "background";
          path = [ pkgs.pueue ];
          execStart = "${scriptPkgs.agentctl}/bin/agentctl pools apply";
          serviceConfig = {
            # PartOf propagates a restart only to a unit that is still active.
            RemainAfterExit = true;
            TimeoutStartSec = "60s";
          };
          unit = {
            after = [ "pueued.service" ];
            requires = [ "pueued.service" ];
            # A daemon that lost its state file comes back with no groups, so
            # the declaration is applied again with every pueued start.
            partOf = [ "pueued.service" ];
            wantedBy = [ "default.target" ];
            # The declaration is in the configuration file rather than in this
            # unit; naming that file is what makes a switch which changed it
            # run this job again.
            restartTriggers = [ configFile ];
          };
        }
      )
      {
        environment.etc."sinnix/agentctl.json".source = configFile;
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
        systemd.tmpfiles.rules = [
          "d ${taskStateRoot} 0700 ${userName} users -"
        ]
        ++ map (path: "d ${path} 0700 ${userName} users -") taskAuthorityParents;
        # Beads' Dolt chunk files use random I/O.  Mark the per-project
        # parent NOCOW before bd creates a fresh authority, which makes the
        # inheritance rule durable without putting mutable task data in Nix.
        system.activationScripts.sinnixBeadsTaskStorage.text = lib.concatMapStringsSep "\n" (path: ''
          ${pkgs.coreutils}/bin/install -d -m 0700 -o ${userName} -g users ${lib.escapeShellArg path}
          if [ "$( ${pkgs.coreutils}/bin/stat -f -c %T ${lib.escapeShellArg path} )" = btrfs ]; then
            ${pkgs.e2fsprogs}/bin/chattr +C ${lib.escapeShellArg path}
          fi
        '') taskAuthorityParents;
        # Launch inputs, bounded logs and typed results of queued jobs.
        sinnix.persistence.home.directories = [ ".local/state/agentctl" ];
      }
    ];
} args
