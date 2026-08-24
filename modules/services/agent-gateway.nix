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
      description = "Private persisted gateway audit and non-job artifact state.";
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
      configFile = jsonFormat.generate "sinnix-agent-gateway.json" {
        inherit (cfg) stateDir maxResultBytes;
        approvedManifestHash = cfg.tunnel.approvedManifestHash;
        approvedActionCatalogHash = cfg.tunnel.approvedActionCatalogHash;
        approvedManifestPrincipal = cfg.tunnel.principal;
        runtimeInventory = "/etc/sinnix/runtime-inventory.json";
        runtimeTransitions = "/run/sinnix/health-transitions.jsonl";
        capabilityIndex = "/etc/sinnix/capability-index.json";
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

      sinnix.runtime.surfaces = lib.optionalAttrs cfg.tunnel.enable {
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
        systemd.user.services.sinnix-agent-gateway-tunnel = lib.mkIf cfg.tunnel.enable {
          Unit = {
            Description = "OpenAI Secure MCP Tunnel to Sinnix ${cfg.tunnel.principal} gateway";
            After = [
              "network-online.target"
              "sinnixd.service"
            ];
            Wants = [ "network-online.target" ];
            Requires = [ "sinnixd.service" ];
            ConditionPathExists = cfg.tunnel.runtimeKeyFile;
            StartLimitIntervalSec = 300;
            StartLimitBurst = 8;
          };
          Service = {
            Type = "simple";
            ExecStartPre = lib.optionals (cfg.tunnel.approvedManifestHash != null) [
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
            ProtectHome = false;
            ReadWritePaths = [
              cfg.stateDir
            ];
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
