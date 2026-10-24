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
in
mkServiceModule {
  name = "agentctl";
  defaultOnDesktop = true;
  description = "agentctl: jobs over pueue, worktrees over worktrunk, gh and bd, and their timers";
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

  extraOptions.pools = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule {
        options = {
          parallel = lib.mkOption {
            type = lib.types.ints.positive;
            description = "How many tasks this pueue group admits at once.";
          };
          adaptive = lib.mkOption {
            default = null;
            description = "Optional headroom-based admission. Parallel is the ceiling.";
            type = lib.types.nullOr (
              lib.types.submodule {
                options = {
                  floor = lib.mkOption { type = lib.types.ints.positive; };
                  jobMemoryBytes = lib.mkOption { type = lib.types.ints.positive; };
                  slice = lib.mkOption { type = lib.types.str; };
                };
              }
            );
          };
          exclusiveWith = lib.mkOption {
            type = lib.types.listOf lib.types.str;
            default = [ ];
            description = "Pools whose live work holds new launches in this pool until they drain.";
          };
        };
      }
    );
    default = {
      # Claude workers that run focused tests in their own process reach
      # 2-3 GiB each; twelve, then eight, held the 8G agentctl-agent slice at
      # 80-95% full memory pressure (2026-09-28), which also paused the pytest
      # pools through pressure pauses. Six fit.
      agent.parallel = 6;
      pytest.parallel = 2;
      pytest-heavy = {
        parallel = 1;
        exclusiveWith = [ "agent" ];
      };
      # Bounded selections stay admissible beside a wave: a worker runs its own
      # focused tests here while its own task occupies the agent pool.
      # Focused jobs run one pytest process. 106 slot receipts (2026-09-27)
      # peaked at p99 553 MiB and max 988 MiB, so eight fit under the quick
      # slice's 9G MemoryHigh even at the observed maximum (six running jobs
      # measured 5.2 GiB together). The width is an interim static bound;
      # sinnix-tisc makes admission follow live headroom.
      pytest-quick = {
        parallel = 8;
        adaptive = {
          floor = 1;
          jobMemoryBytes = 1073741824;
          slice = "agentctl-pytest-quick.slice";
        };
      };
      bulk.parallel = 2;
      # Three Polylogue verify_quick runs fit the 9G normal slice now that one
      # peaks under 1 GiB (polylogue #5754); at 3.3 GiB each they had held it
      # at ~70% full memory pressure.
      normal.parallel = 3;
      # Long-lived development dependencies must not occupy short-job capacity.
      service.parallel = 2;
      interactive.parallel = 4;
      # The gateway's shell.run groups: agent CLIs and commands declared
      # long go to shell-long, so quick commands don't wait behind them.
      shell-quick.parallel = 8;
      # ChatGPT sessions launch 10-60 min `claude -p` workers here
      # (2026-09-29); four at once is what the old shared pool held.
      shell-long.parallel = 4;
    };
    description = "Each pueue group's width and cross-pool admission policy.";
  };

  # No runtime surface: the job plane is pueued (declared by the CLI feature)
  # inside the agentctl slice hierarchy; the units here drive it.
  configFn =
    { cfg, ... }:
    let
      configFile = pkgs.writeText "agentctl.json" (
        builtins.toJSON {
          project_roots = cfg.projectRoots;
          # Foundation owns workstation roots. Long-lived callers may still
          # carry the values exported before a filesystem migration.
          inherited_environment =
            lib.filterAttrs (
              name: _:
              builtins.elem name [
                "LYNCHPIN_REPO_ROOT"
                "SINEX_ROOT"
                "POLYLOGUE_ROOT"
                "SINNIX_ROOT"
                "RAWLOG_FILE"
              ]
            ) config.environment.variables
            // {
              LYNCHPIN_LOCAL_ROOT = "${config.environment.variables.LYNCHPIN_REPO_ROOT}/.lynchpin";
            };
          private_project_catalog = config.sinnix.projects.privateCatalogFile;
          event_spool = eventSpool;
          agentctl = "${scriptPkgs.agentctl}/bin/agentctl";
          pools = lib.mapAttrs (
            _name: pool:
            {
              inherit (pool) parallel;
              exclusive_with = pool.exclusiveWith;
            }
            // lib.optionalAttrs (pool.adaptive != null) {
              adaptive = {
                inherit (pool.adaptive) floor slice;
                job_memory_bytes = pool.adaptive.jobMemoryBytes;
              };
            }
          ) cfg.pools;
        }
      );
    in
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-pressure";
          description = "Reconcile queue admission against memory stall";
        }
        {
          manager = "user";
          resourceClass = "background";
          # The pass pauses and resumes pueue groups through the pueue client.
          path = [ pkgs.pueue ];
          execStart = "${scriptPkgs.agentctl}/bin/agentctl pressure tick";
          serviceConfig = {
            TimeoutStartSec = "30s";
          };
          timer = {
            # Full-stall averages are 60-second means, so sampling faster reads
            # the same number twice. One group is paused or resumed per tick,
            # with the signal-specific order defined by `agentctl pressure tick`.
            intervalSec = 60;
            onBootSec = 60;
            description = "Reconcile queue admission against memory stall";
          };
        }
      )
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-clean";
          description = "Remove finished queue tasks and completed worktrees";
        }
        {
          manager = "user";
          resourceClass = "background";
          # pueued keeps every finished task in memory until it is cleaned;
          # nothing cleaned them, and the daemon grew to 1.2 GB over 3.7 days.
          # Results and receipts stay readable through agentctl afterwards.
          execStart = "${scriptPkgs.agentctl}/bin/agentctl job clean --all-terminal --worktrees";
          serviceConfig = {
            TimeoutStartSec = "5min";
          };
          timer = {
            onCalendar = "*-*-* 05:10:00";
            persistent = true;
            description = "Daily cleanup of finished jobs and completed worktrees";
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
        # Launch inputs, bounded logs and typed results of queued jobs. Owner
        # only: job logs hold whatever a command printed.
        sinnix.persistence.home.directories = [
          {
            directory = ".local/state/agentctl";
            mode = "0700";
          }
        ];
      }
    ];
} args
