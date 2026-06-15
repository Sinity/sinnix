# Trusted local MCP gateway for coding-agent workflows.
#
# Successor to attic/museum/services/chatgpt-mcp.nix. This keeps the useful part
# — a ChatGPT/Codex-reachable local tool substrate — and replaces the old
# ngrok + ssh-mcp shell bridge with a first-class MCP server plus an optional
# local JSON-RPC HTTP endpoint for tunnel experiments.
{
  config,
  lib,
  helpers,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.services.agent-gateway;
  userName = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  jsonFormat = pkgs.formats.json { };

  repositoryType = lib.types.submodule ({ name, ... }: {
    options = {
      url = lib.mkOption {
        type = lib.types.str;
        default = "https://github.com/${name}.git";
        description = "Git remote URL used by repo_materialize.";
      };

      defaultRef = lib.mkOption {
        type = lib.types.str;
        default = "master";
        description = "Default branch/ref checked out by repo_materialize.";
      };

      allowWrite = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Human-facing marker that this repo may be mutated by yolo workflows.";
      };

      env = lib.mkOption {
        type = lib.types.attrsOf lib.types.str;
        default = { };
        description = "Extra environment variables for commands run in this repository.";
      };

      tasks = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = { };
        example = {
          check = [
            "nix"
            "flake"
            "check"
          ];
        };
        description = "Named command vectors exposed through the run_task MCP tool.";
      };
    };
  });

  configFile = jsonFormat.generate "sinnix-agent-gateway-config.json" {
    stateDir = cfg.stateDir;
    auditPath = cfg.auditPath;
    yolo = cfg.yolo;
    allowArbitraryCommands = cfg.allowArbitraryCommands;
    allowedHostCommands = cfg.allowedHostCommands;
    outputLimit = cfg.outputLimit;
    defaultTimeout = cfg.defaultTimeoutSec;
    maxTimeout = cfg.maxTimeoutSec;
    globalEnv = cfg.globalEnv;
    repositories = lib.mapAttrs (_: repo: {
      inherit (repo)
        url
        defaultRef
        allowWrite
        env
        tasks
        ;
    }) cfg.repositories;
  };

  gatewayBin = "${scriptPkgs.sinnix-agent-gateway}/bin/sinnix-agent-gateway";

  mcpWrapper = pkgs.writeShellScriptBin "sinnix-agent-gateway-mcp" ''
    set -euo pipefail
    exec ${gatewayBin} --config ${configFile} stdio
  '';
in
{
  options.sinnix.services.agent-gateway = {
    enable = lib.mkEnableOption "trusted local MCP gateway for repo/code/system agent workflows";

    yolo = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Trusted-operator mode. When true, the gateway defaults to broad local
        coding-agent ergonomics: arbitrary workspace commands are allowed and the
        MCP server behaves like a useful local assistant, not a locked cabinet.
      '';
    };

    allowArbitraryCommands = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Expose run_command for arbitrary commands inside materialized workspaces.";
    };

    allowedHostCommands = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Expose host_run for commands outside a workspace. Keep false for the
        normal coding-agent loop; flip true when deliberately using ChatGPT as a
        local operator surface.
      '';
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/${userName}/.local/state/sinnix-agent-gateway";
      description = "Persistent state root for mirrors, workspaces, jobs, artifacts, and audit logs.";
    };

    auditPath = lib.mkOption {
      type = lib.types.str;
      default = "${cfg.stateDir}/audit.jsonl";
      description = "Append-only JSONL audit ledger path.";
    };

    outputLimit = lib.mkOption {
      type = lib.types.int;
      default = 262144;
      description = "Default maximum stdout/stderr/tool text bytes returned inline.";
    };

    defaultTimeoutSec = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "Default command timeout in seconds.";
    };

    maxTimeoutSec = lib.mkOption {
      type = lib.types.int;
      default = 3600;
      description = "Maximum command timeout accepted by MCP calls.";
    };

    globalEnv = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      description = "Environment variables inherited by gateway-spawned commands.";
    };

    repositories = lib.mkOption {
      type = lib.types.attrsOf repositoryType;
      default = {
        "Sinity/sinnix" = {
          url = "https://github.com/Sinity/sinnix.git";
          defaultRef = "master";
          allowWrite = true;
          tasks = {
            flake-check = [
              "nix"
              "flake"
              "check"
            ];
            eval-prime = [
              "nix"
              "eval"
              ".#nixosConfigurations.sinnix-prime.config.system.build.toplevel.drvPath"
            ];
          };
        };

        "Sinity/sinex" = {
          url = "https://github.com/Sinity/sinex.git";
          defaultRef = "master";
          allowWrite = true;
          tasks = {
            cargo-check = [
              "cargo"
              "check"
              "--workspace"
            ];
            cargo-test = [
              "cargo"
              "test"
              "--workspace"
            ];
            cargo-metadata = [
              "cargo"
              "metadata"
              "--format-version"
              "1"
            ];
          };
        };

        "Sinity/polylogue" = {
          url = "https://github.com/Sinity/polylogue.git";
          defaultRef = "master";
          allowWrite = true;
          tasks = {
            test = [
              "python"
              "-m"
              "pytest"
            ];
          };
        };
      };
      description = "Repositories the gateway can materialize and operate on.";
    };

    http = {
      enable = lib.mkEnableOption "local JSON-RPC HTTP endpoint for tunnel experiments";

      host = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "Host address for the optional HTTP endpoint.";
      };

      port = lib.mkOption {
        type = lib.types.port;
        default = 3020;
        description = "Port for the optional HTTP endpoint.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      scriptPkgs.sinnix-agent-gateway
      mcpWrapper
    ];

    environment.etc."sinnix/agent-gateway/config.json".source = configFile;

    home-manager.users.${userName} = {
      home.file.".config/sinnix-agent-gateway/config.json".source = configFile;

      systemd.user.services.sinnix-agent-gateway-http = lib.mkIf cfg.http.enable {
        Unit = {
          Description = "Sinnix Agent Gateway JSON-RPC HTTP endpoint";
          After = [ "network.target" ];
        };

        Service = {
          ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p ${cfg.stateDir}";
          ExecStart = "${gatewayBin} --config ${configFile} http --host ${cfg.http.host} --port ${toString cfg.http.port}";
          Restart = "on-failure";
          RestartSec = "5s";
          WorkingDirectory = cfg.stateDir;
          Environment = [
            "SINNIX_AGENT_GATEWAY_CONFIG=${configFile}"
            "SINNIX_AGENT_GATEWAY_STATE=${cfg.stateDir}"
          ];
        };

        Install.WantedBy = [ "default.target" ];
      };
    };
  };
}
