# Lynchpin substrate service
#
# Makes the lynchpin-mcp binary available on PATH and sets env vars for
# ergonomic CLI use. No persistent daemon — the MCP server is invoked on
# demand by AI agent runtimes via the stdio transport registered in
# mcp-registry.nix.
#
# Substrate refresh is a daily oneshot systemd timer (Arc E.2).
# When `enable = true` and `refreshTimer.enable = true`, the full DAG
# runs daily and promotes results to the DuckDB substrate so observability
# answers don't lag the week.
#
# Enable with:
#   sinnix.services.lynchpin.enable = true;
#   sinnix.services.lynchpin.refreshTimer.enable = true;
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

    refreshTimer = {
      enable = lib.mkEnableOption "daily substrate refresh timer";

      onCalendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 03:00:00";
        description = "systemd OnCalendar expression for the substrate refresh (daily by default).";
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

    # Optional: daily substrate refresh (Arc E.2).
    # Runs the full analysis DAG + promotes results to DuckDB. The
    # substrate is queryable by MCP clients immediately after.
    systemd.services.lynchpin-refresh = lib.mkIf cfg.refreshTimer.enable {
      description = "Lynchpin analysis DAG refresh";
      after = [ "network.target" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.lynchpin-python}/bin/lynchpin-python -m lynchpin.analysis refresh";
        User = "sinity";
        Group = "users";
        # 4-hour timeout — the full DAG can be heavy.
        TimeoutStartSec = 14400;
      };
    };

    systemd.timers.lynchpin-refresh = lib.mkIf cfg.refreshTimer.enable {
      description = "Daily lynchpin analysis refresh";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.refreshTimer.onCalendar;
        RandomizedDelaySec = toString cfg.refreshTimer.randomizedDelaySec;
        Persistent = true;
      };
    };
  };
}
