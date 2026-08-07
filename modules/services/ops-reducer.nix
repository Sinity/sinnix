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
  reducer = scriptPkgs.sinnix-ops-reducer;
  quota = scriptPkgs.sinnix-quota;
  observe = scriptPkgs.sinnix-observe;
  stateDir = "/realm/state/sinnix-ops";
in
mkServiceModule {
  name = "ops-reducer";
  description = "Sinnix operator current-state reducer and bounded action receipts";
  configFn =
    {
      cfg,
      ...
    }:
    {
      assertions = [
        {
          assertion = cfg.intervalSeconds >= 5;
          message = "sinnix.services.ops-reducer.intervalSeconds must not poll collectors faster than 5 seconds";
        }
      ];
      environment.systemPackages = [ reducer quota quota.passthru.codexbar scriptPkgs.sinnix-pressure-park scriptPkgs.sinnix-rebuild-override scriptPkgs.sinnix-ops-afk-start scriptPkgs.sinnix-ops-afk-resume ];
      systemd.tmpfiles.rules = [ "d /realm/state/sinnix-ops 0700 ${userName} users -" ];
      sinnix.runtime.surfaces.ops-reducer = {
        unit = "sinnix-ops-reducer.service";
        manager = "user";
        resourceClass = "interactive-agent";
        observe = {
          enable = true;
          restartable = true;
        };
        workload = {
          class = "protected";
          kind = "daemon";
          lifecycle = "persistent";
          expendability = "protected";
          operatorProtection = "operator";
          rationale = "Read-only operator snapshot publisher; it never owns lifecycle actions.";
          processMatchers = [ "sinnix-ops-reducer" ];
        };
      };
      home-manager.users.${userName} = {
        home.packages = [ reducer quota quota.passthru.codexbar ];
        systemd.user.sockets.sinnix-ops-reducer = {
          Unit = {
            Description = "Sinnix operator reducer Unix and loopback sockets";
          };
          Socket = {
            ListenStream = [
              "%t/sinnix/ops.sock"
              "127.0.0.1:3090"
            ];
            SocketMode = "0600";
            RemoveOnStop = true;
          };
          Install.WantedBy = [ "sockets.target" ];
        };
        systemd.user.services.sinnix-ops-reducer = {
          Unit = {
            Description = "Sinnix operator current-state reducer and bounded actions";
            After = [ "sinnix-ops-reducer.socket" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${reducer}/bin/sinnix-ops-reducer --runtime-dir %t --state-dir ${stateDir} --inventory /etc/sinnix/runtime-inventory.json --ambient-product /realm/project/sinity-lynchpin/.lynchpin/generated/analysis/ambient_intelligence.json --anchor-events %t/sinnix/afk-resume.json --agent-controller /home/${userName}/.config/hermes/skills/agent-orchestration/scripts/agent_job_control.sh --observe-command ${observe}/bin/sinnix-observe --interval ${toString cfg.intervalSeconds}";
            Restart = "on-failure";
            RestartSec = "2s";
            NoNewPrivileges = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [
              "%t/sinnix"
              stateDir
            ];
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
      description = "Minimum interval between bounded sinnix-observe reads.";
    };
  };
} args
