{
  mkServiceModule,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  hubServer = scriptPkgs.sinnix-hub-server;
  stateDir = "/realm/state/hub";
in
mkServiceModule {
  name = "hub-server";
  defaultOnDesktop = true;
  description = "Sinnix hub server: current machine state and operator actions";
  configFn =
    {
      cfg,
      ...
    }:
    {
      assertions = [
        {
          assertion = cfg.intervalSeconds >= 5;
          message = "sinnix.services.hub-server.intervalSeconds must not poll collectors faster than 5 seconds";
        }
      ];
      environment.systemPackages = [
        hubServer
        scriptPkgs.sinnix-rebuild-override
      ];
      systemd.tmpfiles.rules = [ "d /realm/state/hub 0700 ${userName} users -" ];
      sinnix.runtime.units.hub-server = {
        unit = "sinnix-hub-server.service";
        manager = "user";
        resourceClass = "ordinary";
        notifyOnFailure = true;
        operatorRestart = true;
        workload = {
          class = "protected";
          rationale = "Current-state operator snapshot publisher; it never owns lifecycle actions.";
          processMatchers = [ "sinnix-hub-server" ];
          earlyoomAvoid = true;
        };
      };
      home-manager.users.${userName} = {
        home.packages = [ hubServer ];
        systemd.user.sockets.sinnix-hub-server = {
          Unit = {
            Description = "Sinnix hub server Unix and loopback sockets";
          };
          Socket = {
            ListenStream = [
              "%t/sinnix/hub.sock"
              "127.0.0.1:${toString helpers.data.ports.hubServer}"
            ];
            SocketMode = "0600";
            RemoveOnStop = true;
          };
          Install.WantedBy = [ "sockets.target" ];
        };
        systemd.user.services.sinnix-hub-server = {
          Unit = {
            Description = "Sinnix hub server: current machine state and operator actions";
            # Without Requires, a direct start (login, switch) can beat the
            # socket, which then refuses to bind and 3090 stays closed.
            Requires = [ "sinnix-hub-server.socket" ];
            After = [ "sinnix-hub-server.socket" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${hubServer}/bin/sinnix-hub-server --runtime-dir %t --state-dir ${stateDir} --inventory /etc/sinnix/runtime-inventory.json --clodex-usage /home/${userName}/.clodex/logs/inference-requests.jsonl --ambient-product /realm/project/shared/analysis/lynchpin/ambient_intelligence.json --anchor-events %t/sinnix/afk-resume.json --hyprland-events %t/sinnix/hyprland-events --agentctl ${scriptPkgs.agentctl}/bin/agentctl --interval ${toString cfg.intervalSeconds} --feedback-dir ${cfg.feedbackDir}${
              lib.optionalString (cfg.hubManifest != null) " --hub-manifest ${cfg.hubManifest}"
            }${
              lib.optionalString (
                cfg.rankIngestCommand != null
              ) " --rank-ingest-command ${lib.escapeShellArg (builtins.toJSON cfg.rankIngestCommand)}"
            }";
            # nvidia-smi, journalctl, systemctl and hyprctl are what the pages
            # probe the live host with; /run/current-system/sw/bin is where
            # they are, and the pages render on request rather than from a
            # timer's PATH.
            Environment = [ "PATH=/run/wrappers/bin:/run/current-system/sw/bin" ];
            Restart = "on-failure";
            RestartSec = "2s";
            # The main loop supervises a serial refresh/sweep worker and
            # sends sd_notify without filesystem I/O. The watchdog detects
            # a stalled main loop; slow storage leaves the previous snapshot
            # available instead of forcing a restart.
            NotifyAccess = "main";
            WatchdogSec = "120s";
            NoNewPrivileges = true;
            UMask = "0077";
          };
          Install.WantedBy = [ "default.target" ];
        };
      };
    };
  extraOptions = {
    intervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Interval between lightweight pressure and batched unit observations. Detailed diagnostics run on request.";
    };

    feedbackDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/state/hub-feedback";
      description = ''
        Spool directory for annotations posted to the hub server's /feedback
        route: one append-only JSONL file per UTC day, which agents read
        directly. Set by `sinnix.services.hub`, which owns the route's clients.
      '';
    };

    rankIngestCommand = lib.mkOption {
      type = lib.types.nullOr (lib.types.listOf lib.types.str);
      default = [
        "${scriptPkgs.agentctl}/bin/agentctl"
        "job"
        "start"
        "sinnix"
        "rank_ingest"
        "--wait"
      ];
      description = ''
        AgentCTL argv run, coalesced, when a `sinnix-rank-v1` judgment lands
        in the feedback spool. The default waits for the declared
        `rank_ingest` operation, so completion means the judgments are in
        their domains. Null disables arrival-triggered draining.
      '';
    };

    hubManifest = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Hub manifest (routes, AI roster, frontends) the server-rendered pages
        read. Set by `sinnix.services.hub`, which owns that content; null on a
        host with no hub, whose pages still render from the runtime inventory
        and the hub server's own snapshot.
      '';
    };
  };
} args
