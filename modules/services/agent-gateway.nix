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
  mcpTools = import ../features/dev/agents/mcp-tools.nix {
    inherit
      lib
      pkgs
      scriptPkgs
      config
      ;
  };
  jsonFormat = pkgs.formats.json { };
  gatewayBin = "${scriptPkgs.sinnix-agent-gateway}/bin/sinnix-agent-gateway";
  tunnelClient = scriptPkgs.tunnel-client;
  brokeredMcpServers = [
    "lynchpin"
    "polylogue"
    "sinex"
  ];
  mcpBrokerCommands = {
    lynchpin = "${mcpTools.mcpLynchpinBin}/bin/mcp-lynchpin";
    polylogue = "${mcpTools.mcpPolylogueBin}/bin/mcp-polylogue";
    sinex = "${scriptPkgs.sinnix-mcp-sinex}/bin/sinnix-mcp-sinex";
  };
  mcpBrokerServers = lib.mapAttrs (
    name: server:
    let
      brokered = builtins.elem name brokeredMcpServers;
      profile = (server.profiles or { }).lean or { };
    in
    {
      inherit (server) description transport tier;
      inherit brokered;
    }
    // lib.optionalAttrs brokered {
      command = mcpBrokerCommands.${name};
      args = profile.args or server.args or [ ];
      env = server.env or { };
    }
    // lib.optionalAttrs (!brokered) {
      reason =
        if name == "agent-control" then
          "excluded to avoid recursive gateway job authority"
        else if name == "chrome-devtools" then
          "excluded to preserve gateway-owned browser-target isolation"
        else if server.transport != "stdio" then
          "transport requires an explicit remote credential contract"
        else
          "not admitted to the initial broker route";
    }
  ) helpers.data.mcpRegistry.registry;
in
mkServiceModule {
  name = "agent-gateway";
  description = "principal-scoped MCP gateway over one attested agent-job substrate";
  extraOptions = {
    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/${userName}/.local/state/sinnix/agent-gateway";
      description = "Private persisted gateway audit, artifact, and job state.";
    };
    maxResultBytes = lib.mkOption {
      type = lib.types.int;
      default = 262144;
      description = "Maximum bytes returned by bounded project, observe, and artifact operations.";
    };
    tunnel = {
      enable = lib.mkEnableOption "OpenAI Secure MCP Tunnel";
      principal = lib.mkOption {
        type = lib.types.enum [
          "observer"
          "operator"
        ];
        default = "observer";
        description = "Gateway principal selected explicitly for this tunnel.";
      };
      autoStart = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Start the supervised tunnel at user login.";
      };
      tunnelId = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Non-secret OpenAI tunnel identifier.";
      };
      runtimeKeyFile = lib.mkOption {
        type = lib.types.str;
        default = config.sinnix.secrets.paths."openai-tunnel-runtime-key";
        description = "Agenix runtime key with tunnel Read and Use permissions.";
      };
      healthPort = lib.mkOption {
        type = lib.types.port;
        default = 3088;
        description = "Loopback health, readiness, metrics, and operator UI port.";
      };
      approvedManifestHash = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Frozen ChatGPT connector manifest SHA-256 after publication.";
      };
      approvedActionCatalogHash = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Frozen principal-scoped V2 action catalog SHA-256 after review.";
      };
    };
  };
  configFn =
    { cfg, ... }:
    let
      # dotsRoot-direct, not via the ~/.config/hermes/skills linkFarm hop.
      # Safe against the tunnel's approvedManifestHash: that hashes only the
      # exposed MCP tool schemas (canonical_manifest() in cli.py), and these
      # script paths never appear in a tool's name/description/inputSchema.
      agentController = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-orchestration/scripts/agent_job_control.sh";
      configFile = jsonFormat.generate "sinnix-agent-gateway.json" {
        inherit (cfg) stateDir maxResultBytes;
        approvedManifestHash = cfg.tunnel.approvedManifestHash;
        approvedActionCatalogHash = cfg.tunnel.approvedActionCatalogHash;
        approvedManifestPrincipal = cfg.tunnel.principal;
        runtimeInventory = "/etc/sinnix/runtime-inventory.json";
        capabilityIndex = "/etc/sinnix/capability-index.json";
        agentRunner = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-orchestration/scripts/run_agent_prompt.sh";
        inherit agentController;
        agentScopeExecCommand = "${scriptPkgs.sinnix-agent-scope-exec}/bin/sinnix-agent-scope-exec";
        executionJobCommand = "${scriptPkgs.sinnix-agent-gateway}/bin/sinnix-agent-gateway-execution-job";
        systemdRunCommand = "${pkgs.systemd}/bin/systemd-run";
        systemctlCommand = "${pkgs.systemd}/bin/systemctl";
        observeCommand = "${scriptPkgs.sinnix-observe}/bin/sinnix-observe";
        hyprControlCommand = "/home/${userName}/.local/bin/sinnix-hypr-control";
        screenshotControlCommand = "/home/${userName}/.local/bin/sinnix-screenshot-control";
        kittyControlCommand = "/home/${userName}/.local/bin/sinnix-kitty-control";
        chromeControlCommand = "/home/${userName}/.local/bin/sinnix-chrome-control";
        beadsCommand = "${scriptPkgs.beads}/bin/bd";
        captureCommand = "${scriptPkgs.sinnix-capture}/bin/sinnix-capture";
        mcpBrokerServers = mcpBrokerServers;
        projects = config.sinnix.projects.entries;
      };
      mcpWrapper = pkgs.writeShellScriptBin "sinnix-agent-gateway-mcp" ''
        set -euo pipefail
        principal="observer"
        if [[ ''${1:-} == --principal ]]; then
          principal="''${2:?--principal requires a value}"
          shift 2
        fi
        exec ${gatewayBin} --config ${configFile} --principal "$principal" serve "$@"
      '';
      manifestCheck = pkgs.writeShellScriptBin "sinnix-agent-gateway-schema" ''
        set -euo pipefail
        principal="''${1:-observer}"
        exec ${gatewayBin} --config ${configFile} --principal "$principal" manifest
      '';
      approvalGate = pkgs.writeShellScript "sinnix-agent-gateway-approval-gate" ''
        set -euo pipefail
        exec ${gatewayBin} --config ${configFile} --principal ${lib.escapeShellArg cfg.tunnel.principal} approval-check
      '';
      stateReconcile = pkgs.writeShellScript "sinnix-agent-gateway-state-reconcile" ''
        set -euo pipefail
        ${agentController} --state-dir ${lib.escapeShellArg "${cfg.stateDir}/jobs"} list >/dev/null
      '';
    in
    {
      assertions = [
        {
          assertion = !cfg.tunnel.enable || cfg.tunnel.tunnelId != "";
          message = "sinnix.services.agent-gateway.tunnel.tunnelId must be set when the tunnel is enabled";
        }
        {
          assertion =
            (cfg.tunnel.approvedManifestHash == null) == (cfg.tunnel.approvedActionCatalogHash == null);
          message = "sinnix.services.agent-gateway.tunnel approvals must include both the tool manifest and action catalog hashes";
        }
      ];

      environment.systemPackages = [
        scriptPkgs.sinnix-agent-gateway
        tunnelClient
        mcpWrapper
        manifestCheck
      ];

      environment.etc."sinnix/agent-gateway.json".source = configFile;

      sinnix.persistence.home.directories = [
        {
          directory = ".local/state/sinnix/agent-gateway";
          mode = "0700";
        }
      ];

      sinnix.runtime.surfaces = {
        agent-gateway-jobs = {
          unit = "sinnix-agent-job-.scope";
          manager = "user";
          # A scope, not a "capture". This carried kind = "capture" only to
          # dodge the unit-suffix assertion, and it never needed to: these are
          # real transient systemd scopes and the name ends in .scope. The
          # surface owns its lane in the ordinary way.
          kind = "scope";
          dynamic = true;
          resourceClass = "interactive-agent";
          observe.enable = true;
          workload = {
            class = "protected";
            rationale = "Attested gateway and local agent child scopes.";
            processMatchers = [ "sinnix-agent-job-" ];
          };
          captures = [
            (
              {
                name = "agent-job-manifests";
                path = "${cfg.stateDir}/jobs";
                eventDriven = true;
                # Deliberately NO staleness budget: silence here measures how
                # recently the operator asked for something, not health, so an
                # unused gateway and a broken one look identical. No duration
                # of silence is genuinely suspicious, so make no claim -- the
                # sentinel skips lanes declaring neither cadence nor budget.
                # What silence cannot tell us, the probe below can (sinnix-oig5).
              }
              // lib.optionalAttrs cfg.tunnel.enable {
                # Reachability, asked directly instead of inferred from silence.
                #
                # /readyz rather than /healthz: the tunnel client answers "live"
                # as soon as its process is up, but "ready" only once it holds a
                # working control-plane connection -- and a gateway that is
                # running but disconnected is exactly the state this lane could
                # not previously distinguish from an unused one.
                #
                # Exit codes are chosen for how the sentinel reads them: 0 is
                # healthy, 1 means the source is absent (the honest verdict when
                # the endpoint answers wrong or not at all), and anything else
                # means the probe itself could not answer. curl is addressed by
                # store path because the probe runs under `bash -c` in the user
                # session, where the sentinel's own runtimeInputs are not on
                # PATH; the explicit exit 9 keeps a missing binary from
                # masquerading as a missing gateway.
                #
                # Only declared when the tunnel is enabled. Without it there is
                # no remote gateway to be unreachable, so there would be nothing
                # for a probe to answer.
                livenessProbe = {
                  command =
                    "command -v ${pkgs.curl}/bin/curl >/dev/null || exit 9; "
                    + "${pkgs.curl}/bin/curl -sf -m 5 -o /dev/null "
                    + "http://127.0.0.1:${toString cfg.tunnel.healthPort}/readyz || exit 1";
                  timeoutSeconds = 10;
                };
              }
            )
          ];
        };
      }
      // lib.optionalAttrs cfg.tunnel.enable {
        agent-gateway-tunnel = {
          unit = "sinnix-agent-gateway-tunnel.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe = {
            enable = true;
            restartable = true;
          };
          workload = {
            class = "protected";
            rationale = "Outbound operator control path; bounded and restartable.";
            processMatchers = [ "tunnel-client" ];
          };
        };
      };

      home-manager.users.${userName} = {
        systemd.user.services.sinnix-agent-gateway-reconcile = {
          Unit.Description = "Reconcile Sinnix agent gateway job state";
          Service = {
            Type = "oneshot";
            ExecStart = stateReconcile;
            UMask = "0077";
          };
          Install.WantedBy = [ "default.target" ];
        };
        systemd.user.services.sinnix-agent-gateway-tunnel = lib.mkIf cfg.tunnel.enable {
          Unit = {
            Description = "OpenAI Secure MCP Tunnel to Sinnix ${cfg.tunnel.principal} gateway";
            After = [
              "network-online.target"
              "sinnix-agent-gateway-reconcile.service"
            ];
            Wants = [ "network-online.target" ];
            Requires = [ "sinnix-agent-gateway-reconcile.service" ];
            ConditionPathExists = cfg.tunnel.runtimeKeyFile;
            StartLimitIntervalSec = 300;
            StartLimitBurst = 8;
          };
          Service = {
            Type = "simple";
            ExecStartPre = [
              stateReconcile
            ]
            ++ lib.optionals (cfg.tunnel.approvedManifestHash != null) [
              approvalGate
            ];
            ExecStart = ''
              ${tunnelClient}/bin/tunnel-client run \
                --control-plane.tunnel-id ${lib.escapeShellArg cfg.tunnel.tunnelId} \
                --control-plane.api-key file:%d/runtime-key \
                --mcp.command ${lib.escapeShellArg "command=${mcpWrapper}/bin/sinnix-agent-gateway-mcp --principal ${cfg.tunnel.principal},channel=main"} \
                --health.listen-addr 127.0.0.1:${toString cfg.tunnel.healthPort} \
                --log.format json
            '';
            LoadCredential = "runtime-key:${cfg.tunnel.runtimeKeyFile}";
            Restart = "on-failure";
            RestartSec = "5s";
            # launch_agent() fork/execs claude/codex inside this namespace, so
            # the child inherits this write surface. The observer does not have
            # JOB_START, while operator authority is selected explicitly.
            ProtectHome = false;
            ReadWritePaths = [
              cfg.stateDir
            ]
            ++ lib.sinnix.systemd.agentRuntimeWritePaths { home = "/home/${userName}"; };
            UMask = "0077";
          }
          // lib.optionalAttrs (cfg.tunnel.principal == "observer") {
            NoNewPrivileges = true;
            PrivateTmp = true;
            ProtectSystem = "strict";
          };
          Install.WantedBy = lib.optionals cfg.tunnel.autoStart [ "default.target" ];
        };
      };
    };
} args
