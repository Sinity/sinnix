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
      environment.systemPackages = [
        reducer
        quota
        quota.passthru.codexbar
        scriptPkgs.sinnix-pressure-park
        scriptPkgs.sinnix-rebuild-override
        scriptPkgs.sinnix-ops-afk-start
        scriptPkgs.sinnix-ops-afk-resume
      ];
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
          rationale = "Read-only operator snapshot publisher; it never owns lifecycle actions.";
          processMatchers = [ "sinnix-ops-reducer" ];
          earlyoomAvoid = true;
        };
      };
      home-manager.users.${userName} = {
        home.packages = [
          reducer
          quota
          quota.passthru.codexbar
        ];
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
            # --agent-controller: dotsRoot-direct, not the
            # ~/.config/hermes/skills linkFarm hop.
            ExecStart = "${reducer}/bin/sinnix-ops-reducer --runtime-dir %t --state-dir ${stateDir} --inventory /etc/sinnix/runtime-inventory.json --ambient-product /realm/project/sinity-lynchpin/.lynchpin/generated/analysis/ambient_intelligence.json --anchor-events %t/sinnix/afk-resume.json --hyprland-events %t/sinnix/hyprland-events --agent-controller ${config.sinnix.paths.dotsRoot}/_ai/skills/agent-orchestration/scripts/agent_job_control.sh --observe-command ${observe}/bin/sinnix-observe --interval ${toString cfg.intervalSeconds} --feedback-dir ${cfg.feedbackDir}${lib.optionalString (cfg.hubManifest != null) " --hub-manifest ${cfg.hubManifest}"}${lib.optionalString (cfg.elicitCommand != null) " --elicit-command '${cfg.elicitCommand}'"}";
            # nvidia-smi, journalctl, systemctl and hyprctl are what the pages
            # probe the live host with; /run/current-system/sw/bin is where
            # they are, and the pages render on request rather than from a
            # timer's PATH.
            Environment = [ "PATH=/run/wrappers/bin:/run/current-system/sw/bin" ];
            Restart = "on-failure";
            RestartSec = "2s";
            NoNewPrivileges = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [
              "%t/sinnix"
              stateDir
              # The annotation spool the /feedback route appends to. Nothing
              # else under /realm/data is writable from here.
              cfg.feedbackDir
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

    feedbackDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/derived/hub-feedback";
      description = ''
        Spool directory for annotations posted to the reducer's /feedback
        route: one append-only JSONL file per UTC day, which agents read
        directly. Set by `sinnix.services.hub`, which owns the route's clients.
      '';
    };

    elicitCommand = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Command run, coalesced, when a `sinnix-elicit-v1` record lands in the
        feedback spool — replacing the 120s drain timer with the arrival that
        made it necessary. Null means nothing is triggered.
      '';
    };

    hubManifest = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Hub manifest (routes, AI roster, frontends) the server-rendered pages
        read. Set by `sinnix.services.hub`, which owns that content; null on a
        host with no hub, whose pages still render from the runtime inventory
        and the reducer's own snapshot.
      '';
    };
  };
} args
