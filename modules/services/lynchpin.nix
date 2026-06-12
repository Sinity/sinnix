# Lynchpin substrate service
#
# Makes the lynchpin-mcp binary available on PATH and sets env vars for
# ergonomic CLI use. No persistent daemon — the MCP server is invoked on
# demand by AI agent runtimes via the stdio transport registered in
# mcp-registry.nix.
#
# Substrate materialization is a daily oneshot systemd timer (Arc E.2).
# When `enable = true` and `materializationTimer.enable = true`, the full DAG
# runs daily and promotes results to the DuckDB substrate so observability
# answers don't lag the week.
#
# Enable with:
#   sinnix.services.lynchpin.enable = true;
#   sinnix.services.lynchpin.materializationTimer.enable = true;
{
  config,
  lib,
  helpers,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.services.lynchpin;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
{
  options.sinnix.services.lynchpin = {
    enable = lib.mkEnableOption "lynchpin substrate + MCP server";

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

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      scriptPkgs.lynchpin-cli
      scriptPkgs.lynchpin-python
    ];

    environment.variables = {
      LYNCHPIN_MCP_PROVIDED = "1";
    };

    # Optional: daily substrate materialization (Arc E.2).
    # Runs the full analysis DAG + promotes results to DuckDB. The
    # substrate is queryable by MCP clients immediately after.
    systemd.services.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
      description = "Lynchpin analysis DAG materialization";
      after = [ "network.target" ];
      # The materialization CLI resolves `.lynchpin/` relative to its working
      # directory (repo-rooted, like git). Without WorkingDirectory the unit
      # ran from `/` and failed nightly with
      # `PermissionError: [Errno 13] Permission denied: '.lynchpin'`, silently
      # freezing the analysis substrate. Pin CWD and the root env vars.
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.lynchpin-python}/bin/lynchpin-python -m lynchpin.analysis materialize";
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
}
