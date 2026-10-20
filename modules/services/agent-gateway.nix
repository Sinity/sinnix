# The OpenAI Secure MCP endpoint for the operator's own ChatGPT.
#
# Single-user and operator-only: the gateway has the operator's full power by
# design. Remote shells and jobs run with the operator's environment, API keys
# included; those secrets stay on this host (docs/agent-gateway.md, Authority).
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
      callTimeoutSeconds = server.callTimeoutSeconds or 30;
      sessionPolicy = server.gatewaySessionPolicy or "per-call";
    }
    // lib.optionalAttrs brokered {
      command = mcpBrokerCommands.${name};
      args = profile.args or server.args or [ ];
      env = server.env or { };
      readOnlyRoutes = server.gatewayReadOnlyRoutes or [ ];
      readOnlyTools = server.gatewayReadOnlyTools or [ ];
    }
    // lib.optionalAttrs (!brokered) {
      reason =
        if name == "chrome-devtools" then
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
  description = "operator MCP gateway";
  extraOptions = {
    stateDir = lib.mkOption {
      type = lib.types.str;
      # The path predates single-endpoint configuration; it holds the audit
      # database, results and artifacts.
      default = "/home/${userName}/.local/state/sinnix/agent-gateway/operator";
      description = "Private persisted gateway audit, result and artifact state.";
    };
    maxResultBytes = lib.mkOption {
      type = lib.types.int;
      default = 262144;
      description = "Client response byte budget. Larger successful payloads use artifacts; chunked read operations also use this budget. This is not a Beads owner-output limit.";
    };
    autoStart = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Start the tunnel and its MCP server at user login.";
    };
    projects = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Canonical project IDs the gateway serves; empty means every configured project.";
    };
    tunnelId = lib.mkOption {
      type = lib.types.str;
      description = "Non-secret OpenAI tunnel identifier.";
    };
    runtimeKeyFile = lib.mkOption {
      type = lib.types.str;
      default = "/run/agenix/openai-tunnel-runtime-key";
      description = "Agenix runtime key of the OpenAI tunnel.";
    };
    healthPort = lib.mkOption {
      type = lib.types.port;
      default = 3088;
      description = "Loopback health, readiness, metrics, and UI port of the tunnel client.";
    };
  };
  configFn =
    { cfg, ... }:
    let
      configFile = jsonFormat.generate "sinnix-agent-gateway.json" {
        inherit (cfg) stateDir maxResultBytes;
        endpoint.scope.projects = cfg.projects;
        projects = config.sinnix.projects.entries;
        privateProjectCatalogFile = config.sinnix.projects.privateCatalogFile;
        inherit mcpBrokerServers;
        packageManifestPath = "${scriptPkgs.sinnix-agent-gateway}/share/sinnix-agent-gateway/manifest.json";
      };
      manifestCheck = pkgs.writeShellScriptBin "sinnix-agent-gateway-schema" ''
        set -euo pipefail
        exec ${gatewayBin} --config ${configFile} manifest
      '';
      manifestGate = pkgs.writeShellScript "sinnix-agent-gateway-manifest-check" ''
        set -euo pipefail
        exec ${gatewayBin} --config ${configFile} manifest-check
      '';
      selfTest = pkgs.writeShellScript "sinnix-agent-gateway-self-test" ''
        set -euo pipefail
        exec ${gatewayBin} --config ${configFile} self-test
      '';
      stateScaffold = pkgs.writeShellScript "sinnix-agent-gateway-state-scaffold" ''
        set -euo pipefail
        exec ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArg cfg.stateDir}
      '';
      gatewayPath =
        lib.makeBinPath [
          pkgs.systemd
          scriptPkgs.sinnix-runtime # sinnix-observe
          scriptPkgs.beads
          scriptPkgs.sinnix-capture
        ]
        # Desktop adapters are managed out-of-store scripts. Their shebangs
        # and tools must see the same profiles as the graphical user session.
        # Keep the explicit paths above: capture is not necessarily installed
        # into either profile. AgentCTL tools come from the packaged wrapper.
        + ":/run/current-system/sw/bin:/etc/profiles/per-user/${userName}/bin"
        + ":/home/${userName}/.local/bin";
      giTypelibPath = "${pkgs.at-spi2-core}/lib/girepository-1.0:${pkgs.gobject-introspection}/lib/girepository-1.0";
    in
    {

      environment.systemPackages = [
        scriptPkgs.sinnix-agent-gateway
        tunnelClient
        manifestCheck
      ];

      environment.etc."sinnix/agent-gateway.json".source = configFile;

      sinnix.persistence.home.directories = [
        {
          directory = ".local/state/sinnix/agent-gateway";
          mode = "0700";
        }
      ];

      sinnix.runtime.units = {
        agent-gateway = {
          unit = "sinnix-agent-gateway.service";
          manager = "user";
          resourceClass = "ordinary";
          notifyOnFailure = true;
          operatorRestart = true;
          workload = {
            class = "protected";
            rationale = "Outbound operator control path; independently bounded and restartable.";
            processMatchers = [ "tunnel-client" ];
          };
          activation = {
            mode = "direct";
            publicEndpoint = "127.0.0.1:${toString cfg.healthPort}";
          };
        };
        agent-gateway-mcp = {
          unit = "sinnix-agent-gateway-mcp.service";
          manager = "user";
          resourceClass = "ordinary";
          notifyOnFailure = true;
          operatorRestart = true;
          workload = {
            class = "protected";
            rationale = "Loopback MCP server for the operator tunnel.";
            processMatchers = [ "sinnix-agent-gateway" ];
          };
          # The server runs a remote agent's tools in process: git and
          # content reads over checkouts, owner subprocesses, and the
          # brokered MCP children. That is agent tool work, so it shares
          # agenttool.slice's budget instead of running unbounded in
          # app.slice, and MemoryHigh throttles this unit first. Page cache
          # from checkout reads is what reclaim takes: one night of
          # all-worktree content hashing charged 9.4G here.
          # MemoryMax is the safety boundary for remote-driven work: memory
          # that reclaim cannot take past MemoryHigh is a runaway call, and
          # the kernel ends it here instead of in the operator's session.
          # TimeoutStopSec covers the server's own 8 s drain deadline.
          resources = {
            Slice = "agenttool.slice";
            MemoryHigh = "4G";
            MemoryMax = "6G";
            TimeoutStopSec = "10s";
          };
          activation = {
            mode = "direct";
          };
        };
      };

      home-manager.users.${userName} = {
        systemd.user.services = {
          sinnix-agent-gateway = {
            Unit = {
              Description = "OpenAI Secure MCP tunnel for the Sinnix gateway";
              After = [
                "network-online.target"
                "sinnix-agent-gateway-mcp.service"
              ];
              Wants = [
                "network-online.target"
                "sinnix-agent-gateway-mcp.service"
              ];
              ConditionPathExists = cfg.runtimeKeyFile;
              StartLimitIntervalSec = 300;
              StartLimitBurst = 8;
            };
            Service = {
              Type = "simple";
              # The client dispatches at most this many commands to the
              # server at once (default 10); the rest queue inside it while
              # the control plane's per-command response deadline runs. A
              # ChatGPT fleet of 16 tabs exceeds 10.
              ExecStart = ''
                ${tunnelClient}/bin/tunnel-client run \
                  --control-plane.tunnel-id ${lib.escapeShellArg cfg.tunnelId} \
                  --control-plane.api-key file:%d/runtime-key \
                  --mcp.server-url ${lib.escapeShellArg "url=http://localhost:8000/mcp,channel=main,unix-socket=%t/sinnix-agent-gateway/mcp.sock"} \
                  --mcp.startup-wait-timeout 30s \
                  --mcp.max-concurrent-requests 32 \
                  --health.listen-addr 127.0.0.1:${toString cfg.healthPort} \
                  --log.format json \
                  --log.level warn
              '';
              LoadCredential = "runtime-key:${cfg.runtimeKeyFile}";
              Restart = "always";
              RestartSec = "5s";
              UMask = "0077";
              # warn: at info the client logs its whole dependency graph on
              # every start plus a line per dispatched call.
              # No gateway PATH or typelib path. The client does start
              # `codex app-server` (from the user manager's PATH) to serve
              # Codex over the tunnel; the codex wrapper scopes it under
              # agent.slice. Every input of this unit must be the tunnel's own, since
              # Home Manager restarts a unit whose file changed and a
              # tunnel restart drops every in-flight call. A restart of the
              # server alone does not: the client reconnects to its socket.
            };
            Install.WantedBy = lib.optionals cfg.autoStart [ "default.target" ];
          };
          sinnix-agent-gateway-mcp = {
            Unit = {
              Description = "Loopback MCP server for the Sinnix gateway";
              StartLimitIntervalSec = 300;
              StartLimitBurst = 8;
            };
            Service =
              lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                unit = "sinnix-agent-gateway-mcp.service";
                manager = "user";
              }
              // {
                Type = "simple";
                RuntimeDirectory = "sinnix-agent-gateway";
                RuntimeDirectoryMode = "0700";
                ExecStartPre = [
                  stateScaffold
                  manifestGate
                  selfTest
                ];
                ExecStart = ''
                  ${gatewayBin} --config ${configFile} serve-http --socket %t/sinnix-agent-gateway/mcp.sock
                '';
                Restart = "always";
                RestartSec = "5s";
                UMask = "0077";
                Environment = [
                  "PATH=${gatewayPath}"
                  "GI_TYPELIB_PATH=${giTypelibPath}"
                ];
              };
            Install.WantedBy = lib.optionals cfg.autoStart [ "default.target" ];
          };
        };
      };
    };
} args
