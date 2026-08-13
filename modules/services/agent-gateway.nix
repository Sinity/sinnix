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
  jsonFormat = pkgs.formats.json { };
  gatewayBin = "${scriptPkgs.sinnix-agent-gateway}/bin/sinnix-agent-gateway";
  tunnelClient = scriptPkgs.tunnel-client;
in
mkServiceModule {
  name = "agent-gateway";
  description = "capability-profiled MCP gateway over one attested agent-job substrate";
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
      enable = lib.mkEnableOption "OpenAI Secure MCP Tunnel for the remote-readonly profile";
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
        runtimeInventory = "/etc/sinnix/runtime-inventory.json";
        agentRunner = "${config.sinnix.paths.dotsRoot}/_ai/skills/agent-orchestration/scripts/run_agent_prompt.sh";
        inherit agentController;
        observeCommand = "${scriptPkgs.sinnix-observe}/bin/sinnix-observe";
        projects = config.sinnix.projects.entries;
      };
      mcpWrapper = pkgs.writeShellScriptBin "sinnix-agent-gateway-mcp" ''
        set -euo pipefail
        profile="remote-readonly"
        if [[ ''${1:-} == --profile ]]; then
          profile="''${2:?--profile requires a value}"
          shift 2
        fi
        exec ${gatewayBin} --config ${configFile} --profile "$profile" serve "$@"
      '';
      manifestCheck = pkgs.writeShellScriptBin "sinnix-agent-gateway-schema" ''
        set -euo pipefail
        profile="''${1:-remote-readonly}"
        exec ${gatewayBin} --config ${configFile} --profile "$profile" manifest
      '';
      approvedManifestGate = pkgs.writeShellScript "sinnix-agent-gateway-manifest-gate" ''
        set -euo pipefail
        actual="$(${gatewayBin} --config ${configFile} --profile remote-readonly manifest | ${pkgs.jq}/bin/jq -r .sha256)"
        expected=${
          lib.escapeShellArg (
            if cfg.tunnel.approvedManifestHash == null then "" else cfg.tunnel.approvedManifestHash
          )
        }
        if [[ "$actual" != "$expected" ]]; then
          echo "remote-readonly tool manifest drift: expected $expected, got $actual" >&2
          exit 1
        fi
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
          kind = "capture";
          dynamic = true;
          resourceClass = "interactive-agent";
          observe.enable = true;
          workload = {
            class = "protected";
            rationale = "Attested gateway and local agent child scopes.";
            processMatchers = [ "sinnix-agent-job-" ];
          };
          captures = [
            {
              name = "agent-job-manifests";
              path = "${cfg.stateDir}/jobs";
              eventDriven = true;
              staleAfterSeconds = 3600;
            }
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
            Description = "OpenAI Secure MCP Tunnel to Sinnix remote-readonly gateway";
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
              approvedManifestGate
            ];
            ExecStart = ''
              ${tunnelClient}/bin/tunnel-client run \
                --control-plane.tunnel-id ${lib.escapeShellArg cfg.tunnel.tunnelId} \
                --control-plane.api-key file:%d/runtime-key \
                --mcp.command ${lib.escapeShellArg "command=${mcpWrapper}/bin/sinnix-agent-gateway-mcp --profile remote-readonly,channel=main"} \
                --health.listen-addr 127.0.0.1:${toString cfg.tunnel.healthPort} \
                --log.format json
            '';
            LoadCredential = "runtime-key:${cfg.tunnel.runtimeKeyFile}";
            Restart = "on-failure";
            RestartSec = "5s";
            NoNewPrivileges = true;
            PrivateTmp = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [ cfg.stateDir ];
            UMask = "0077";
          };
          Install.WantedBy = lib.optionals cfg.tunnel.autoStart [ "default.target" ];
        };
      };
    };
} args
