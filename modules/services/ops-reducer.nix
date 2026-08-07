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
  description = "Read-only Sinnix operator current-state reducer";
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
      environment.systemPackages = [ reducer quota quota.passthru.codexbar ];
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
            Description = "Sinnix read-only operator current-state reducer";
            After = [ "sinnix-ops-reducer.socket" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${reducer}/bin/sinnix-ops-reducer --runtime-dir %t --state-dir ${stateDir} --observe-command ${observe}/bin/sinnix-observe --interval ${toString cfg.intervalSeconds}";
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
