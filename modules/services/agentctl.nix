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
        };
      }
    );
    # Widths keep builds efficient inside the job plane's memory ceiling
    # (agent-ctl.slice, runtime-defaults.nix); the ceiling, not the widths,
    # keeps the host alive. Jobs beyond what the plane holds are throttled
    # and then killed, which wastes their work, so the memory-heavy pools
    # admit what fits: one test build beside one check.
    default = {
      # Claude workers running focused tests reach 2-3 GiB each.
      agent.parallel = 2;
      # Codex workers, ~136 MB each, mostly wait on builds in other pools;
      # sixteen fit their slice's 3G MemoryHigh.
      codex.parallel = 16;
      pytest.parallel = 1;
      pytest-heavy.parallel = 1;
      # Focused jobs run one pytest process (p99 about 550 MiB, max about
      # 1 GiB), so four fit under the quick slice's 4G MemoryHigh.
      pytest-quick.parallel = 4;
      # Focused Cargo test builds, 2-7 GiB each: one at a time. /realm also
      # sustains only 25-50 MB/s of writes, and each test build writes 1-6 GB.
      normal.parallel = 1;
      # Full checks and arbitrary commands, the longest builds: one at a time.
      bulk.parallel = 1;
      # Long-lived development dependencies must not occupy short-job capacity.
      service.parallel = 2;
      interactive.parallel = 2;
      # The gateway's shell.run groups: agent CLIs and commands declared
      # long go to shell-long, so quick commands don't wait behind them.
      shell-quick.parallel = 4;
      # ChatGPT sessions launch 10-60 minute Claude workers here, 2-3 GiB each.
      shell-long.parallel = 2;
      # Long I/O-heavy maintenance (copies between disks, offloads) that must
      # yield the disk to builds and interactive work; its slice carries the
      # lowest I/O weight in the job plane.
      background.parallel = 2;
      # Measurements and full system builds each get a slot outside bulk, so
      # checks can run beside them; prebuilt benchmarks use `measure_run`.
      measure.parallel = 1;
      system-build.parallel = 1;
      # Rust type and lint checks (3-4 GiB each) have their own pool, so they
      # never wait behind test builds; one runs beside a test build.
      compile.parallel = 1;
    };
    description = "Each pueue group's width and cross-pool admission policy.";
  };

  extraOptions.buildOutputExempt = lib.mkOption {
    type = lib.types.listOf lib.types.str;
    # Checkouts of a campaign in progress, whose owner manages their build
    # output. Empty this list when that campaign ends.
    default = [
      "pl-*"
      "sx-*"
      "common-*"
      "sinnix-a"
      "sinnix-b"
      "sinnix-budget"
    ];
    description = "Worktree directory names (shell patterns) that `agentctl worktree build-output` lists by name only: their build output is never sized or removed.";
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
          pools = lib.mapAttrs (_name: pool: { inherit (pool) parallel; }) cfg.pools;
          build_output_exempt = cfg.buildOutputExempt;
          # What `job start --discretionary` asks before it queues a job.
          quota_check = [
            "${scriptPkgs.sinnix-quota}/bin/sinnix-quota"
            "ok"
            "--for"
            "discretionary"
            "--json"
          ];
        }
      );
    in
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "agentctl-clean-queue";
          description = "Remove finished queue tasks";
        }
        {
          manager = "user";
          resourceClass = "background";
          # Keep the most recent 24 hours of task IDs while releasing older
          # queue rows. Inputs and output stay in agentctl's state directory.
          execStart = "${scriptPkgs.agentctl}/bin/agentctl job clean --all-terminal";
          serviceConfig = {
            TimeoutStartSec = "5min";
          };
          timer = {
            onCalendar = "hourly";
            persistent = true;
            description = "Hourly cleanup of queue tasks finished over 24 hours ago";
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
