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
  description = "principal-scoped MCP gateway over attested agent-job endpoints";
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
    endpoints = lib.mkOption {
      type = lib.types.attrsOf (
        lib.types.submodule (
          { name, ... }:
          {
            options = {
              enable = lib.mkEnableOption "this OpenAI Secure MCP endpoint";
              principal = lib.mkOption {
                type = lib.types.enum [
                  "observer"
                  "operator"
                ];
                default = "observer";
                description = "Gateway principal selected explicitly for this endpoint.";
              };
              label = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Optional human-readable endpoint label.";
              };
              autoStart = lib.mkOption {
                type = lib.types.bool;
                default = true;
                description = "Start this supervised endpoint at user login.";
              };
              stateDir = lib.mkOption {
                type = lib.types.str;
                default = "/home/${userName}/.local/state/sinnix/agent-gateway/${name}";
                description = "Private persisted state for this endpoint.";
              };
              scope = {
                projects = lib.mkOption {
                  type = lib.types.listOf lib.types.str;
                  default = [ ];
                  description = "Canonical project IDs visible to this endpoint.";
                };
                captures = lib.mkOption {
                  type = lib.types.listOf lib.types.str;
                  default = [ ];
                  description = "Capture lane or subject scopes visible to this endpoint.";
                };
              };
              tunnelId = lib.mkOption {
                type = lib.types.str;
                default = "";
                description = "Non-secret OpenAI tunnel identifier for this endpoint.";
              };
              runtimeKeyFile = lib.mkOption {
                type = lib.types.str;
                default = "/run/agenix/openai-tunnel-runtime-key-${name}";
                description = "Agenix runtime key dedicated to this endpoint.";
              };
              healthPort = lib.mkOption {
                type = lib.types.port;
                default = 3088;
                description = "Loopback health, readiness, metrics, and UI port.";
              };
              approvedManifestHash = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Frozen endpoint tool manifest SHA-256 after publication.";
              };
              approvedActionCatalogHash = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Frozen endpoint action catalog SHA-256 after review.";
              };
            };
          }
        )
      );
      default = { };
      description = "Independently supervised principal-scoped gateway endpoints.";
    };
  };
  configFn =
    { cfg, ... }:
    let
      enabledEndpoints = lib.filterAttrs (_: endpoint: endpoint.enable) cfg.endpoints;
      endpointProjects =
        endpoint:
        lib.filterAttrs (
          projectId: _: endpoint.scope.projects == [ ] || builtins.elem projectId endpoint.scope.projects
        ) config.sinnix.projects.entries;
      endpointConfigs = lib.mapAttrs (
        name: endpoint:
        jsonFormat.generate "sinnix-agent-gateway-${name}.json" {
          stateDir = endpoint.stateDir;
          inherit (cfg) maxResultBytes;
          endpoint = {
            inherit name;
            label = endpoint.label;
            principal = endpoint.principal;
            scope = endpoint.scope;
          };
          approvedManifestHash = endpoint.approvedManifestHash;
          approvedActionCatalogHash = endpoint.approvedActionCatalogHash;
          approvedManifestPrincipal = endpoint.principal;
          runtimeInventory = "/etc/sinnix/runtime-inventory.json";
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
          projects = endpointProjects endpoint;
        }
      ) enabledEndpoints;
      endpointArtifacts = lib.mapAttrs (
        name: endpoint:
        let
          configFile = endpointConfigs.${name};
        in
        {
          mcpWrapper = pkgs.writeShellScriptBin "sinnix-agent-gateway-${name}-mcp" ''
            set -euo pipefail
            exec ${gatewayBin} --config ${configFile} --principal ${lib.escapeShellArg endpoint.principal} serve "$@"
          '';
          manifestCheck = pkgs.writeShellScriptBin "sinnix-agent-gateway-${name}-schema" ''
            set -euo pipefail
            exec ${gatewayBin} --config ${configFile} --principal ${lib.escapeShellArg endpoint.principal} manifest
          '';
          approvalGate = pkgs.writeShellScript "sinnix-agent-gateway-${name}-approval-gate" ''
            set -euo pipefail
            exec ${gatewayBin} --config ${configFile} --principal ${lib.escapeShellArg endpoint.principal} approval-check
          '';
          stateScaffold = pkgs.writeShellScript "sinnix-agent-gateway-${name}-state-scaffold" ''
            set -euo pipefail
            exec ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArg endpoint.stateDir}
          '';
        }
      ) enabledEndpoints;
      endpointValues = lib.mapAttrsToList (_: endpoint: endpoint) enabledEndpoints;
      duplicateValues =
        field:
        let
          values = map (endpoint: toString endpoint.${field}) endpointValues;
        in
        lib.filter (value: builtins.length (builtins.filter (candidate: candidate == value) values) > 1) (
          lib.unique values
        );
      invalidProjects = lib.concatLists (
        lib.mapAttrsToList (
          name: endpoint:
          map (projectId: "${name}:${projectId}") (
            lib.filter (
              projectId: !(builtins.hasAttr projectId config.sinnix.projects.entries)
            ) endpoint.scope.projects
          )
        ) enabledEndpoints
      );
    in
    {
      assertions = [
        {
          assertion = invalidProjects == [ ];
          message = "agent-gateway endpoint scopes name unknown projects: ${lib.concatStringsSep ", " invalidProjects}";
        }
        {
          assertion = duplicateValues "tunnelId" == [ ];
          message = "agent-gateway endpoints must use distinct tunnel IDs";
        }
        {
          assertion = duplicateValues "runtimeKeyFile" == [ ];
          message = "agent-gateway endpoints must use distinct runtime credentials";
        }
        {
          assertion = duplicateValues "healthPort" == [ ];
          message = "agent-gateway endpoints must use distinct health ports";
        }
      ]
      ++ lib.concatLists (
        lib.mapAttrsToList (name: endpoint: [
          {
            assertion = endpoint.tunnelId != "";
            message = "sinnix.services.agent-gateway.endpoints.${name}.tunnelId must be set when the endpoint is enabled";
          }
          {
            assertion = endpoint.approvedManifestHash != null && endpoint.approvedActionCatalogHash != null;
            message = "sinnix.services.agent-gateway.endpoints.${name} requires both manifest and action catalog approvals";
          }
        ]) enabledEndpoints
      );

      environment.systemPackages = [
        scriptPkgs.sinnix-agent-gateway
        tunnelClient
      ]
      ++ lib.concatLists (
        lib.mapAttrsToList (name: _: [
          endpointArtifacts.${name}.mcpWrapper
          endpointArtifacts.${name}.manifestCheck
        ]) enabledEndpoints
      );

      environment.etc = lib.mapAttrs' (
        name: _:
        lib.nameValuePair "sinnix/agent-gateway-${name}.json" {
          source = endpointConfigs.${name};
        }
      ) enabledEndpoints;

      sinnix.persistence.home.directories = [
        {
          directory = ".local/state/sinnix/agent-gateway";
          mode = "0700";
        }
      ];

      sinnix.runtime.surfaces = lib.mapAttrs' (
        name: endpoint:
        lib.nameValuePair "agent-gateway-${name}" {
          unit = "sinnix-agent-gateway-${name}.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe = {
            enable = true;
            restartable = true;
          };
          workload = {
            class = "protected";
            rationale = "Outbound ${endpoint.principal} control path for endpoint ${name}; independently bounded and restartable.";
            processMatchers = [ "tunnel-client" ];
          };
          activation = {
            mode = "direct";
            publicEndpoint = "127.0.0.1:${toString endpoint.healthPort}";
          };
        }
      ) enabledEndpoints;

      home-manager.users.${userName} = {
        systemd.user.services = lib.mapAttrs' (
          name: endpoint:
          lib.nameValuePair "sinnix-agent-gateway-${name}" {
            Unit = {
              Description = "OpenAI Secure MCP endpoint ${name} for Sinnix ${endpoint.principal} gateway";
              After = [
                "network-online.target"
                "sinnixd.service"
              ];
              Wants = [ "network-online.target" ];
              Requires = [ "sinnixd.service" ];
              ConditionPathExists = endpoint.runtimeKeyFile;
              StartLimitIntervalSec = 300;
              StartLimitBurst = 8;
            };
            Service = {
              Type = "simple";
              ExecStartPre = [
                endpointArtifacts.${name}.stateScaffold
                endpointArtifacts.${name}.approvalGate
              ];
              ExecStart = ''
                ${tunnelClient}/bin/tunnel-client run \
                  --control-plane.tunnel-id ${lib.escapeShellArg endpoint.tunnelId} \
                  --control-plane.api-key file:%d/runtime-key \
                  --mcp.command ${lib.escapeShellArg "command=${endpointArtifacts.${name}.mcpWrapper}/bin/sinnix-agent-gateway-${name}-mcp,channel=main"} \
                  --health.listen-addr 127.0.0.1:${toString endpoint.healthPort} \
                  --log.format json
              '';
              LoadCredential = "runtime-key:${endpoint.runtimeKeyFile}";
              Restart = "on-failure";
              RestartSec = "5s";
              ProtectHome = false;
              ReadWritePaths = [
                "-${endpoint.stateDir}"
              ];
              UMask = "0077";
            }
            // lib.optionalAttrs (endpoint.principal == "observer") {
              NoNewPrivileges = true;
              PrivateTmp = true;
              ProtectSystem = "strict";
            };
            Install.WantedBy = lib.optionals endpoint.autoStart [ "default.target" ];
          }
        ) enabledEndpoints;
      };
    };
} args
