# Hermes Agent — multi-provider AI agent.
#
# Sinnix owns the executable wrapper, persistent state, and declarative config.
# Auth remains user-stateful because OAuth/device flows are interactive.
{
  config,
  inputs,
  lib,
  pkgs,
  helpers,
  ...
}:
let
  cfg = config.sinnix.services.hermes;
  userName = config.sinnix.user.name;
  system = pkgs.stdenv.hostPlatform.system;
  hermesPkg = inputs.llm-agents.packages.${system}.hermes-agent;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  yamlFormat = pkgs.formats.yaml { };
  mcpRegistry = import ../lib/mcp-registry.nix { inherit lib; };

  hermesMcpServers = lib.mapAttrs mcpRegistry.renderHermesServer (
    mcpRegistry.selectClientServers "hermes"
  );

  hermesConfig = yamlFormat.generate "hermes-config.yaml" {
    model = {
      default = cfg.model;
      provider = cfg.provider;
    };
    fallback_providers = cfg.fallbackProviders;
    terminal.cwd = cfg.workingDirectory;
    checkpoints = {
      enabled = true;
      max_snapshots = 1000000;
    };
    memory = {
      memory_enabled = true;
      user_profile_enabled = true;
      memory_char_limit = 8000;
      user_char_limit = 4000;
    };
    delegation = {
      model = cfg.model;
      provider = cfg.provider;
    };
    approvals = {
      mode = cfg.approvals.mode;
    };
    agent = {
      max_turns = 1000000;
      api_max_retries = 3;
    };
    context.project_discovery = true;
    mcp_servers = hermesMcpServers;
  };

  agentScopePrelude = ''
    run_agent_scoped() {
      if [[ -z "''${SINNIX_AGENT_SCOPED:-}" ]]; then
        scope_bin="${scriptPkgs.sinnix-scope}/bin/sinnix-scope"
        if [[ ! -x "$scope_bin" ]]; then
          scope_bin="$(command -v sinnix-scope 2>/dev/null || true)"
        fi
        if [[ -n "$scope_bin" && -x "$scope_bin" ]]; then
          exec "$scope_bin" background -- ${pkgs.coreutils}/bin/env SINNIX_AGENT_SCOPED=1 "$@"
        fi
      fi

      exec "$@"
    }
  '';
in
{
  options.sinnix.services.hermes = {
    enable = lib.mkEnableOption "Hermes AI Agent";

    package = lib.mkOption {
      type = lib.types.package;
      default = hermesPkg;
      description = "Hermes package used by the managed CLI wrapper.";
    };

    provider = lib.mkOption {
      type = lib.types.str;
      default = "deepseek";
      description = "Primary Hermes inference provider.";
    };

    model = lib.mkOption {
      type = lib.types.str;
      default = "deepseek-v4-pro";
      description = "Primary Hermes model.";
    };

    fallbackProviders = lib.mkOption {
      type = lib.types.listOf (
        lib.types.submodule {
          options = {
            provider = lib.mkOption { type = lib.types.str; };
            model = lib.mkOption { type = lib.types.str; };
          };
        }
      );
      default = [
        {
          provider = "openai-codex";
          model = "gpt-5.5";
        }
      ];
      description = "Hermes fallback provider chain.";
    };

    workingDirectory = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.realmRoot}/project";
      description = "Default working directory used by Hermes terminal tools.";
    };

    approvals = {
      mode = lib.mkOption {
        type = lib.types.enum [
          "manual"
          "smart"
          "off"
        ];
        default = "manual";
        description = "Dangerous command approval mode. 'manual' prompts user, 'smart' uses auxiliary LLM, 'off' auto-approves all commands (YOLO).";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    sinnix = {
      features.dev.mcp-servers.enable = lib.mkDefault true;
      persistence.home.directories = [
        {
          directory = ".hermes";
          mode = "0700";
        }
      ];
    };

    home-manager.users.${userName} = {
      home.file = {
        ".hermes/config.yaml" = {
          source = hermesConfig;
          force = true;
        };

        ".local/bin/hermes" = {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            HERMES_BIN="${cfg.package}/bin/hermes"
            unset PYTHONPATH PYTHONHOME PYTHONBREAKPOINT PYTHONUSERBASE VIRTUAL_ENV
            export PYTHONNOUSERSITE=1

            ${agentScopePrelude}

            run_agent_scoped "$HERMES_BIN" "$@"
          '';
          executable = true;
          force = true;
        };
      };
    };
  };
}
