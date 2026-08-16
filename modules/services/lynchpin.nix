# Lynchpin substrate service
#
# Makes the lynchpin-mcp binary available on PATH and sets env vars for
# ergonomic CLI use. No persistent daemon — the MCP server is invoked on
# demand by AI agent runtimes via the stdio transport registered in
# mcp-registry.nix.
#
# Substrate materialization is a daily oneshot systemd timer.
# When `enable = true` and `materializationTimer.enable = true`, the full DAG
# runs daily and promotes results to the DuckDB substrate so observability
# answers don't lag the week.
#
# Enable with:
#   sinnix.services.lynchpin.enable = true;
#   sinnix.services.lynchpin.materializationTimer.enable = true;
{
  mkServiceModule,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "lynchpin";
  description = "lynchpin substrate + MCP server";
  extraOptions = {
    repoRoot = lib.mkOption {
      type = lib.types.str;
      default = "/realm/project/sinity-lynchpin";
      description = ''
        Absolute path to the lynchpin checkout. The materialization CLI is
        repo-rooted: it reads/writes `.lynchpin/` relative to this directory.
        Used as the service WorkingDirectory and to export
        LYNCHPIN_REPO_ROOT/LYNCHPIN_LOCAL_ROOT so the job does not depend on
        the process's inherited CWD.
      '';
    };

    materializationTimer = {
      enable = lib.mkEnableOption "daily substrate materialization timer";

      onCalendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 03:00:00";
        description = "systemd OnCalendar expression for substrate materialization (daily by default).";
      };

      randomizedDelaySec = lib.mkOption {
        type = lib.types.int;
        default = 3600;
        description = "Max randomized delay in seconds (spreads load).";
      };
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      localRoot = "${cfg.repoRoot}/.lynchpin";
      # github_context shells out to `gh`, which authenticates from
      # GITHUB_TOKEN. A systemd unit sources no profile.d, so the agenix
      # export every interactive shell gets is not there -- resolve the
      # secret explicitly and exec the CLI.
      materializeEntrypoint = pkgs.writeShellApplication {
        name = "lynchpin-materialize-entrypoint";
        runtimeInputs = [ pkgs.coreutils ];
        text = ''
          ${lib.sinnix.mkSecretLookup {
            secretName = "github-token";
            caller = "lynchpin-materialize";
          }}
          exec ${scriptPkgs.lynchpin-python}/bin/lynchpin-python -m lynchpin.cli.materialize --all
        '';
      };
      localHotDirs = [
        "cache"
        "duck"
        "enrich"
        "refresh"
      ];
      localHotDirArgs = lib.concatMapStringsSep " " (
        dir: lib.escapeShellArg "${localRoot}/${dir}"
      ) localHotDirs;
    in
    {
      environment.systemPackages = [
        scriptPkgs.lynchpin-cli
        scriptPkgs.lynchpin-python
      ];

      environment.variables = {
        LYNCHPIN_MCP_PROVIDED = "1";
      };

      systemd.services.lynchpin-local-attrs = {
        description = "Prepare Lynchpin local cache directories";
        wantedBy = [ "multi-user.target" ];
        path = [
          pkgs.coreutils
          pkgs.e2fsprogs
        ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          install -d -m 0775 -o sinity -g users ${lib.escapeShellArg localRoot}
          for dir in ${localHotDirArgs}; do
            install -d -m 0775 -o sinity -g users "$dir"
            chattr +C "$dir" || true
          done
        '';
      };

      # Optional: daily substrate materialization.
      # Runs the full analysis DAG + promotes results to DuckDB. The
      # substrate is queryable by MCP clients immediately after.
      systemd.services.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Lynchpin analysis DAG materialization";
        # A broken ExecStart here fails silently every night; route failures
        # to the desktop like the backup jobs do.
        onFailure = [ "sinnix-service-failure-notify@%n.service" ];
        requires = [ "lynchpin-local-attrs.service" ];
        after = [
          "network.target"
          "lynchpin-local-attrs.service"
        ];
        path = [
          pkgs.git
          # github_context calls `gh` via shutil.which and records
          # "gh_not_found" for every repo when it is absent -- which is
          # exactly what it did, nightly, unnoticed, until a different
          # failure earlier in the DAG stopped it from getting this far.
          pkgs.gh
        ];
        # The materialization CLI resolves `.lynchpin/` relative to its working
        # directory (repo-rooted, like git), so without WorkingDirectory the
        # unit runs from `/` and dies on PermissionError. Pin CWD and the root
        # env vars.
        serviceConfig = {
          Type = "oneshot";
          # `lynchpin.analysis materialize` is not a valid subcommand; the
          # transparent-DAG runner is lynchpin.cli.materialize (requires
          # explicit --all).
          ExecStart = "${materializeEntrypoint}/bin/lynchpin-materialize-entrypoint";
          User = "sinity";
          Group = "users";
          WorkingDirectory = cfg.repoRoot;
          Environment = [
            "LYNCHPIN_REPO_ROOT=${cfg.repoRoot}"
            "LYNCHPIN_LOCAL_ROOT=${cfg.repoRoot}/.lynchpin"
          ];
          # 4-hour timeout — the full DAG can be heavy.
          TimeoutStartSec = 14400;
        };
      };

      # The webhistory lane belongs here, to the unit that actually fills it.
      # It used to be declared in capture-registry.nix against a
      # `sinnix-capture-webhistory` unit that does not exist, which is how a
      # lane could carry a 48h staleness budget with nothing on any schedule
      # able to keep it -- see sinnix-ksws. Registering the surface also puts
      # this daily job in front of the health sentinel, which it was not.
      sinnix.runtime.surfaces.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        unit = "lynchpin-materialize.service";
        resourceClass = "background-maintenance";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Daily analysis DAG and browser-history capture; rerunnable at will.";
        };
        captures = [
          {
            name = "webhistory";
            path = "${config.sinnix.paths.capturesRoot}/webhistory";
            eventDriven = true;
            # Two days against a daily timer: one missed run is tolerable,
            # two is worth surfacing. The hard deadline is far longer --
            # Chrome drops visits after ~90 days -- so this is an early
            # warning, not the edge of data loss.
            staleAfterSeconds = 172800;
          }
        ];
      };

      systemd.timers.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Daily lynchpin analysis materialization";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = cfg.materializationTimer.onCalendar;
          RandomizedDelaySec = toString cfg.materializationTimer.randomizedDelaySec;
          Persistent = true;
        };
      };
    };
} args
