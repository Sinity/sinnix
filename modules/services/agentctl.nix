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
  stateDir = "${config.sinnix.paths.stateRoot}/agentctl";
  eventSpool = "${stateDir}/events.jsonl";
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
      # 2-3 GiB each; twelve, then eight, held the 8G agent-ctl-agent slice at
      # 80-95% full memory pressure (2026-09-28), which also paused the pytest
      # pools through pressure pauses. Six fit.
      agent.parallel = 6;
      # Codex workers: light, mostly waiting on builds in other pools, so
      # the fleet is sized by available work, not by cores (2026-10-27).
      # 40 (2026-10-27 15:40) filled zram completely by 16:06 (5 MB free,
      # 3.1 GB available) next to the job plane's builds; 32 recovered it.
      codex.parallel = 32;
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
          slice = "agent-ctl-pytest-quick.slice";
        };
      };
      # The widths of the pools that run Cargo builds (normal, bulk, compile)
      # are the bound on concurrent builds: a job takes its queue slot only
      # when it can run. Together they admit four, one of them a
      # metadata-only check. Two focused builds peak at about 6.2G each
      # (Sinex focused compile, 2026-11-02) and fit the normal slice's 12G
      # MemoryHigh, so an overrun is throttled or killed inside that slice.
      # At one wide, normal held eight queued jobs (retro 20, 2026-11-02);
      # at two beside other load on 11-02 05:13-06:34, oomd killed a focused
      # compile, so this width stays under observation (sinnix-rerqe).
      normal.parallel = 2;
      # Full checks and arbitrary commands, the longest builds: one at a time.
      bulk.parallel = 1;
      # Long-lived development dependencies must not occupy short-job capacity.
      service.parallel = 2;
      interactive.parallel = 4;
      # The gateway's shell.run groups: agent CLIs and commands declared
      # long go to shell-long, so quick commands don't wait behind them.
      shell-quick.parallel = 8;
      # ChatGPT sessions launch 10-60 min `claude -p` workers here
      # (2026-09-29); four at once is what the old shared pool held.
      shell-long.parallel = 4;
      # Long I/O-heavy maintenance (copies between disks, offloads) that must
      # yield the disk to builds and interactive work; its slice carries the
      # lowest I/O weight in the job plane.
      background.parallel = 2;
      # Measurements and full system builds: long jobs that held bulk slots
      # while the checks gating merges queued behind them. A slot each,
      # outside bulk. A measurement that compiles uses `measure`; restores and
      # benchmarks of prebuilt binaries use `measure_run`.
      measure.parallel = 1;
      system-build.parallel = 1;
      # Rust type and lint checks of a lane's change (`compile`, Clippy)
      # write only metadata and take 1-4 minutes. In their own pool they
      # never wait behind test builds or for a pause of `normal` and `bulk`,
      # so a head is known to compile before it is pushed or sent to a cloud
      # check.
      compile.parallel = 1;
      # The master baselines' warm builds, which take 23-60 minutes. Their own
      # slot, so they never hold one that lanes wait for; one at a time, at
      # the plane's lowest build weights.
      baseline.parallel = 1;
    };
    description = "Each pueue group's width and cross-pool admission policy.";
  };

  extraOptions.masterBaselines = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    default = [
      "polylogue"
      "sinex"
    ];
    description = "Projects whose `baseline` operation runs on each new default-branch head, in a reserved checkout whose target also seeds new checkouts' Cargo targets.";
  };

  # No runtime surface: the job plane is pueued (declared by the CLI feature)
  # inside the agent-ctl slice hierarchy; the units here drive it.
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
          # Not the yielding background class: at Nice 10 and IO priority 7 the
          # tick starved during the very stalls it exists to answer, and timed
          # out 14 times over the 10-18..10-27 boot.
          resourceClass = "ordinary";
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
          unitName = "agentctl-clean-queue";
          description = "Remove finished queue tasks";
        }
        {
          manager = "user";
          resourceClass = "background";
          # Every `pueue status --json` serialises all retained tasks, and the
          # pressure tick, the hub and agentctl ask many times a minute; the
          # daemon's memory follows the largest response. Daily cleaning let
          # ~900 finished tasks a day pile up (349 MB on 2026-10-27, 1.2 GB
          # over 3.7 days before any cleaning), and freed tasks do not return
          # the allocator's high-water mark, so clean often enough that the
          # queue never grows large. Worktree retirement stays daily below.
          execStart = "${scriptPkgs.agentctl}/bin/agentctl job clean --all-terminal";
          serviceConfig = {
            TimeoutStartSec = "5min";
          };
          timer = {
            onCalendar = "hourly";
            persistent = true;
            description = "Hourly cleanup of finished queue tasks";
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
          # Each pass retires at most one batch per project and stops admitting
          # removals after 45 minutes, inside the start timeout; deferred
          # checkouts go in the next pass.
          execStart = "${scriptPkgs.agentctl}/bin/agentctl job clean --all-terminal --worktrees --budget-seconds 2700";
          # The worktree holder census reads hidden process working
          # directories through the host's noninteractive sudo wrapper.
          path = [ "/run/wrappers" ];
          serviceConfig = {
            # With a working census each candidate's holder scan and removal
            # take real time on a loaded host; 5 minutes cut the first run off.
            TimeoutStartSec = "1h";
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
        # The project list is configuration, so the units merge below the
        # top-level `systemd` attribute rather than as list items.
        systemd = lib.mkMerge (
          map (
            project:
            (lib.sinnix.mkScheduledJob
              {
                inherit config;
                unitName = "agentctl-baseline-${project}";
                description = "Queue the ${project} baseline on a new default-branch head";
              }
              {
                manager = "user";
                resourceClass = "background";
                execStart = "${scriptPkgs.sinnix-master-baseline}/bin/sinnix-master-baseline ${project}";
                # The queued job inherits this PATH: Nix, the system tools and the
                # user profile's sinnix-cargo-target, as in a login shell.
                path = [
                  "/run/wrappers"
                  "/etc/profiles/per-user/${userName}"
                  "/run/current-system/sw"
                ];
                serviceConfig = {
                  # Fetch and enqueue only; the operation owns the build's timeout.
                  TimeoutStartSec = "5min";
                };
                timer = {
                  intervalSec = 600;
                  onBootSec = 600;
                  description = "Queue the ${project} baseline on a new default-branch head";
                };
              }
            ).systemd
          ) cfg.masterBaselines
        );
      }
      {
        environment.etc."sinnix/agentctl.json".source = configFile;
        # Queued commands and the timers run with the system PATH, not an
        # interactive profile, so the tools agentctl shells out to must be
        # system packages.
        environment.systemPackages = [
          scriptPkgs.agentctl
          config.system.build.polylogueCli
          pkgs.worktrunk
          pkgs.pueue
          pkgs.gh
        ];
        systemd.tmpfiles.rules = [
          "d ${taskStateRoot} 0700 ${userName} users -"
          # Launch inputs, logs, outcomes and typed results of queued jobs.
          # Owner only: job logs hold whatever a command printed. They live on
          # Realm rather than the wear-limited root disk, at the path that
          # agentctl and every recorded launch input name.
          "d ${stateDir} 0700 ${userName} users -"
          "L ${config.users.users.${userName}.home}/.local/state/agentctl - - - - ${stateDir}"
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
      }
    ];
} args
