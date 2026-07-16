# AI agent CLI wrappers (claude/codex/gemini/agy/hermes), shared skills, and
# per-agent runtime state. Wrapper-builder machinery lives in backends.nix.
{
  mkFeatureModule,
  lib,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "agentTools"
  ];
  description = "AI agent CLIs, shared skills, and runtime state";
  extraOptions.hermesConfigSource = lib.mkOption {
    type = lib.types.path;
    internal = true;
    description = "Path to the generated default Hermes configuration (for tests)";
  };
  extraOptions.hermesProfileConfigSources = lib.mkOption {
    type = lib.types.attrsOf lib.types.path;
    internal = true;
    description = "Paths to generated mode-specific Hermes configurations (for tests)";
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      helpers,
      user,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      agentRuntimePackages = [
        scriptPkgs.beads
      ]
      ++ (with pkgs; [
        nodejs_22
        git
        bash
        gnutar
        gzip
        which
        coreutils
        gcc
      ]);
      agentRuntimePath = lib.makeBinPath agentRuntimePackages;
      hermesRuntimePath = lib.makeBinPath (
        agentRuntimePackages
        ++ (with pkgs; [
          uv
          python313
          ripgrep
          ffmpeg
          portaudio
        ])
      );

      sinnixCfg = config.sinnix;

      # Runtime path of the agenix-decrypted DeepSeek API key (read at launch by
      # the deepseek wrappers; falls back gracefully when the secret is absent).
      deepseekSecretPath = lib.attrByPath [
        "sinnix"
        "secrets"
        "paths"
        "deepseek-api-key"
      ] "/run/agenix/deepseek-api-key" config;

      jsonFormat = pkgs.formats.json { };
      yamlFormat = pkgs.formats.yaml { };
      inherit (helpers.data) mcpRegistry;
      hermesMcpServers = lib.mapAttrs mcpRegistry.renderHermesServer (
        mcpRegistry.selectClientServersForProfile "evidence" "hermes"
      );
      hermesResearchMcpServers = lib.mapAttrs mcpRegistry.renderHermesServer (
        mcpRegistry.selectClientServersForProfile "browser" "hermes"
      );
      hermesOrchestrateMcpServers = lib.mapAttrs mcpRegistry.renderHermesServer (
        mcpRegistry.selectClientServersForProfile "orchestrate" "hermes"
      );
      mkHermesConfig =
        {
          name,
          toolsets,
          mcpServers ? hermesMcpServers,
          reasoningEffort ? "medium",
          delegation ? { },
          voiceEnabled ? true,
        }:
        yamlFormat.generate "hermes-${name}-config.yaml" {
          _config_version = 33;
          model = {
            default = "gpt-5.6-terra";
            provider = "openai-codex";
          };
          fallback_providers = [
            {
              provider = "gemini";
              model = "gemini-2.5-flash";
            }
          ];
          terminal = {
            backend = "local";
            cwd = ".";
            timeout = 180;
            home_mode = "auto";
          };
          agent = {
            max_turns = 100;
            verify_on_stop = true;
            reasoning_effort = reasoningEffort;
          };
          approvals.mode = "off";
          memory = {
            memory_enabled = true;
            user_profile_enabled = true;
            memory_char_limit = 8000;
            user_char_limit = 4500;
            nudge_interval = 10;
            flush_min_turns = 6;
          };
          skills = {
            creation_nudge_interval = 15;
            external_dirs = [
              "/home/${user}/.config/hermes/skills"
              "/home/${user}/.hermes/skills"
            ];
          };
          plugins.enabled = [ "observability/nemo_relay" ];
          delegation = {
            max_iterations = 100;
            max_concurrent_children = 3;
            max_spawn_depth = 1;
          }
          // delegation;
          platform_toolsets.cli = toolsets;
          mcp_servers = mcpServers;
          voice = {
            record_key = "ctrl+b";
            max_recording_seconds = 120;
            auto_tts = voiceEnabled;
            beep_enabled = voiceEnabled;
            silence_threshold = 200;
            silence_duration = 1.2;
          };
          stt = {
            enabled = voiceEnabled;
            provider = "local";
            local.model = "base";
          };
          tts = {
            provider = "edge";
            edge.voice = "en-US-AriaNeural";
          };
          updates = {
            pre_update_backup = true;
            backup_keep = 5;
            non_interactive_local_changes = "stash";
          };
        };
      hermesConfigFile = mkHermesConfig {
        name = "default";
        toolsets = [ "hermes-cli" ];
      };
      hermesResearchConfigFile = mkHermesConfig {
        name = "research";
        mcpServers = hermesResearchMcpServers;
        toolsets = [
          "web"
          "browser"
          "file"
          "skills"
          "todo"
          "memory"
          "session_search"
          "code_execution"
          "delegation"
          "clarify"
        ];
        reasoningEffort = "high";
        delegation = {
          max_iterations = 60;
          max_concurrent_children = 6;
          max_spawn_depth = 1;
        };
        voiceEnabled = false;
      };
      hermesOrchestrateConfigFile = mkHermesConfig {
        name = "orchestrate";
        mcpServers = hermesOrchestrateMcpServers;
        toolsets = [ "skills" "todo" "memory" "session_search" "clarify" ];
        reasoningEffort = "high";
        voiceEnabled = false;
      };
      hermesMirrorConfigFile = mkHermesConfig {
        name = "mirror";
        toolsets = [ "skills" "todo" "memory" "session_search" "clarify" "tts" ];
      };
      claudeMcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
        mcpRegistry.selectClientServersForProfile "full" "claude"
      );
      claudeLeanMcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
        mcpRegistry.selectClientServersForProfile "lean" "claude"
      );
      claudeBrowserMcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
        mcpRegistry.selectClientServersForProfile "browser" "claude"
      );
      # Dedicated registry-driven MCP config consumed via `claude --mcp-config`.
      # Claude Code 2.x does NOT read `mcpServers` from settings.json — only
      # `.mcp.json` (project), `~/.claude.json` (user, managed by `claude mcp add`),
      # or `--mcp-config <file>` recognise stdio servers. This file is the
      # registry's connection point.
      claudeMcpConfigFile = jsonFormat.generate "claude-mcp.json" {
        mcpServers = claudeMcpServers;
      };
      claudeLeanMcpConfigFile = jsonFormat.generate "claude-mcp-lean.json" {
        mcpServers = claudeLeanMcpServers;
      };
      claudeBrowserMcpConfigFile = jsonFormat.generate "claude-mcp-browser.json" {
        mcpServers = claudeBrowserMcpServers;
      };
      sharedSkillNames = import ../../../../flake/data/shared-agent-skills.nix;
      sharedSkillFarm = pkgs.linkFarm "sinnix-shared-agent-skills" (
        map (name: {
          inherit name;
          path = inputs.self + "/dots/_ai/skills/${name}";
        }) sharedSkillNames
      );
      # Runs the given launcher under sinnix-scope's agent slice unless already
      # scoped (see scripts/sinnix-agent-scope-exec).
      agentScopeExec = "${scriptPkgs.sinnix-agent-scope-exec}/bin/sinnix-agent-scope-exec";

      backends = import ./backends.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          agentRuntimePath
          hermesRuntimePath
          agentScopeExec
          sinnixCfg
          user
          ;
      };
      inherit (backends)
        mkNpmBootstrap
        mkClaudeCodeWrapper
        mkCodexWrapper
        hermesBootstrap
        ensureHermes
        hermesConfigureLocal
        mkHermesWrapper
        ;
    in
    {
      sinnix.features.dev.agentTools.hermesConfigSource = hermesConfigFile;
      sinnix.features.dev.agentTools.hermesProfileConfigSources = {
        research = hermesResearchConfigFile;
        orchestrate = hermesOrchestrateConfigFile;
        mirror = hermesMirrorConfigFile;
      };
      sinnix.persistence.home = {
        directories = [
          {
            directory = ".config/claude";
            mode = "0700";
          }
          {
            directory = ".codex";
            mode = "0700";
          }
          {
            directory = ".gemini";
            mode = "0700";
          }
          # npm installs survive impermanence cold boots so agents do not
          # re-download on every activation.
          ".local/state/claude-code"
          ".local/state/codex"
          ".local/state/gemini"
          ".hermes"
        ];
        files = [ ".claude.json" ];
      };

      home-manager.users.${user} =
        {
          config,
          lib,
          mkDotsFileFor,
          ...
        }:
        let
          mkDotsFile = mkDotsFileFor config;
        in
        {
          home.packages = [
            scriptPkgs.beads
            scriptPkgs.sinnix-scope
            scriptPkgs.sinnix-agent-scope-exec
            scriptPkgs.chatgpt-share-export
            scriptPkgs.verify-agent-topology
            scriptPkgs.sinnix-agent-control-mcp
          ];

          programs.zsh = {
            shellAliases = {
              # `claude` routes through claude-full (NOT a bare ~/.local/bin/claude):
              # Claude Code's native local-installer claims the literal path
              # ~/.local/bin/claude and clobbers any symlink there on auto-update,
              # which is what repeatedly broke the bare command. Suffixed names are
              # never touched, so the wrapper lives at claude-full and the alias
              # points here.
              claude = "~/.local/bin/claude-full";
              claude-lean = "~/.local/bin/claude-lean";
              claude-browser = "~/.local/bin/claude-browser";
              claude-deepseek = "~/.local/bin/claude-deepseek";
              claude-local = "~/.local/bin/claude-local";
              codex = "~/.local/bin/codex";
              codex-lean = "~/.local/bin/codex-lean";
              codex-full = "~/.local/bin/codex-full";
              codex-browser = "~/.local/bin/codex-browser";
              codex-deepseek = "~/.local/bin/codex-deepseek";
              codex-local = "~/.local/bin/codex-local";
              gemini = "~/.local/bin/gemini";
              agy = "~/.local/bin/agy-sinnix";
              hermes = "~/.local/bin/hermes";
              hermes-research = "~/.local/bin/hermes-research";
              hermes-orchestrate = "~/.local/bin/hermes-orchestrate";
              hermes-mirror = "~/.local/bin/hermes-mirror";
              hermes-local = "~/.local/bin/hermes-local";
              hermes-acp = "~/.local/bin/hermes-acp";
              hermes-update = "~/.local/bin/hermes-update";
            };
          };

          xdg.configFile = {
            "claude/hooks/pretooluse-bash.sh".source = mkDotsFile "/claude/hooks/pretooluse-bash.sh";
            "claude/hooks/sessionstart-polylogue-recall.sh".source =
              mkDotsFile "/claude/hooks/sessionstart-polylogue-recall.sh";
            "claude/hooks/sessionstart-sinex-recall.sh" = {
              text = builtins.readFile ../../../../dots/claude/hooks/sessionstart-sinex-recall.sh;
              executable = true;
            };
            "claude/hooks/sessionstart-beads-prime.sh".source =
              mkDotsFile "/claude/hooks/sessionstart-beads-prime.sh";
            # Registry-driven MCP config consumed by the claude wrapper.
            "claude/mcp.json".source = claudeMcpConfigFile;
            "claude/mcp-lean.json".source = claudeLeanMcpConfigFile;
            "claude/mcp-browser.json".source = claudeBrowserMcpConfigFile;
            "claude/CLAUDE.md".source = mkDotsFile "/claude/CLAUDE.md";
            "claude/skills" = {
              source = sharedSkillFarm;
              force = true;
            };
          };

          home.activation.claudeSymlink = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p $HOME/.config/claude
            ln -sfn .config/claude $HOME/.claude
            ln -sfn ${sinnixCfg.paths.dotsRoot}/claude/settings.json $HOME/.config/claude/settings.json
          '';
          home.activation.hermesConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            mkdir -p "$HOME/.hermes"
            cp ${hermesConfigFile} "$HOME/.hermes/config.yaml"
            chmod 600 "$HOME/.hermes/config.yaml"

            for profile in research orchestrate mirror; do
              mkdir -p "$HOME/.hermes/profiles/$profile"
              ln -sfn ../../auth.json "$HOME/.hermes/profiles/$profile/auth.json"
              ln -sfn ../../.env "$HOME/.hermes/profiles/$profile/.env"
              ln -sfn ../../SOUL.md "$HOME/.hermes/profiles/$profile/SOUL.md"
            done
            cp ${hermesResearchConfigFile} "$HOME/.hermes/profiles/research/config.yaml"
            cp ${hermesOrchestrateConfigFile} "$HOME/.hermes/profiles/orchestrate/config.yaml"
            cp ${hermesMirrorConfigFile} "$HOME/.hermes/profiles/mirror/config.yaml"
            chmod 600 "$HOME/.hermes/profiles/research/config.yaml" \
              "$HOME/.hermes/profiles/orchestrate/config.yaml" \
              "$HOME/.hermes/profiles/mirror/config.yaml"
          '';
          # Codex/Gemini read the global instruction file directly; CLAUDE.md is
          # flat (no @-transclusion), so a symlink replaces the old render step
          # and can never go stale between activations.
          home.activation.linkGlobalAgentInstructions = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p "$HOME/.codex" "$HOME/.gemini"
            ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.codex/AGENTS.md"
            ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.gemini/GEMINI.md"
          '';

          # Full/default profile. Named claude-full (not claude) so Claude Code's
          # native local-installer can't clobber it; the `claude` alias points here.
          home.file.".local/bin/claude-full" = mkClaudeCodeWrapper { };
          home.file.".local/bin/claude-lean" = mkClaudeCodeWrapper {
            mcpConfigName = "mcp-lean";
          };
          home.file.".local/bin/claude-browser" = mkClaudeCodeWrapper {
            mcpConfigName = "mcp-browser";
          };

          # DeepSeek through the real Claude Code harness via its native
          # Anthropic-compatible endpoint. Full/default MCP profile.
          home.file.".local/bin/claude-deepseek" = mkClaudeCodeWrapper {
            extraEnv = ''
              if [ ! -r ${lib.escapeShellArg deepseekSecretPath} ]; then
                echo "claude-deepseek: cannot read ${deepseekSecretPath}" >&2
                exit 1
              fi
              export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
              ANTHROPIC_AUTH_TOKEN="$(<${lib.escapeShellArg deepseekSecretPath})"
              export ANTHROPIC_AUTH_TOKEN
              DEEPSEEK_MODEL="deepseek-chat"
              export ANTHROPIC_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_OPUS_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_SONNET_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_HAIKU_MODEL="$DEEPSEEK_MODEL"
              export CLAUDE_CODE_SUBAGENT_MODEL="$DEEPSEEK_MODEL"
            '';
          };

          # Local models through the real Claude Code harness, via the LiteLLM
          # gateway that translates Anthropic ↔ OpenAI (modules/services/litellm.nix).
          # Full/default MCP profile. Model names are defined in that module's
          # model_list; keep ANTHROPIC_MODEL in sync with an entry there.
          home.file.".local/bin/claude-local" = mkClaudeCodeWrapper {
            extraEnv = ''
              export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
              # LiteLLM binds loopback with no master key; Claude Code still
              # requires a non-empty token, so send a dummy.
              export ANTHROPIC_AUTH_TOKEN="sk-local"
              LOCAL_MODEL="local-llama"
              export ANTHROPIC_MODEL="$LOCAL_MODEL"
              export ANTHROPIC_DEFAULT_OPUS_MODEL="$LOCAL_MODEL"
              export ANTHROPIC_DEFAULT_SONNET_MODEL="$LOCAL_MODEL"
              export ANTHROPIC_DEFAULT_HAIKU_MODEL="$LOCAL_MODEL"
              export CLAUDE_CODE_SUBAGENT_MODEL="$LOCAL_MODEL"
            '';
          };

          home.file.".local/bin/sessionstart-sinex-recall" = {
            text = ''
              #!${pkgs.runtimeShell}
              exec "$HOME/.claude/hooks/sessionstart-sinex-recall.sh" "$@"
            '';
            executable = true;
            force = true;
          };

          home.file.".local/bin/codex" = mkCodexWrapper { profile = "full"; };
          home.file.".local/bin/codex-lean" = mkCodexWrapper { profile = "lean"; };
          home.file.".local/bin/codex-full" = mkCodexWrapper { profile = "full"; };
          home.file.".local/bin/codex-browser" = mkCodexWrapper { profile = "browser"; };

          # DeepSeek / local through Codex. The layered <profile>.config.toml
          # (generated in mcp.nix's client-profiles.nix) carries the model +
          # model_provider + full MCP table; the wrapper only supplies the
          # provider API key env.
          home.file.".local/bin/codex-deepseek" = mkCodexWrapper {
            profile = "deepseek";
            extraEnv = ''
              if [ ! -r ${lib.escapeShellArg deepseekSecretPath} ]; then
                echo "codex-deepseek: cannot read ${deepseekSecretPath}" >&2
                exit 1
              fi
              DEEPSEEK_API_KEY="$(<${lib.escapeShellArg deepseekSecretPath})"
              export DEEPSEEK_API_KEY
            '';
          };
          home.file.".local/bin/codex-local" = mkCodexWrapper {
            profile = "local";
            # LiteLLM needs no real key on loopback; the provider's env_key must
            # still resolve to a non-empty value.
            extraEnv = ''export LITELLM_LOCAL_KEY="sk-local"'';
          };

          home.file.".local/bin/gemini" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              ${mkNpmBootstrap {
                stateDir = "gemini";
                npmPackage = "@google/gemini-cli";
                binaryName = "gemini";
              }}

              exec ${agentScopeExec} "$STATE/launch.sh" "$@"
            '';
            executable = true;
            force = true;
          };

          # The vendor-managed ~/.local/bin/agy self-updates. Keep it as the
          # canonical binary and route interactive shell use through this
          # distinct wrapper so Antigravity jobs get the same agent.slice
          # containment as the other terminal agents.
          home.file.".local/bin/agy-sinnix" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail
              exec ${agentScopeExec} "$HOME/.local/bin/agy" "$@"
            '';
            executable = true;
            force = true;
          };

          home.file.".config/hermes/skills" = {
            source = sharedSkillFarm;
            force = true;
          };
          home.file.".local/bin/hermes" = mkHermesWrapper { };
          home.file.".local/bin/hermes-research" = mkHermesWrapper { profile = "research"; };
          home.file.".local/bin/hermes-orchestrate" = mkHermesWrapper { profile = "orchestrate"; };
          home.file.".local/bin/hermes-mirror" = mkHermesWrapper { profile = "mirror"; };
          home.file.".local/bin/hermes-acp" = mkHermesWrapper {
            entrypoint = "hermes-acp";
          };
          home.file.".local/bin/hermes-local" = mkHermesWrapper {
            extraPrelude = ''
              export OPENAI_BASE_URL="http://127.0.0.1:4000/v1"
              export OPENAI_API_KEY="sk-local"
              ${hermesConfigureLocal}
            '';
          };
          home.file.".local/bin/hermes-update" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              ${hermesBootstrap}

              ${ensureHermes}
              git -C "$HERMES_INSTALL_DIR" pull --ff-only
              (
                cd "$HERMES_INSTALL_DIR"
                UV_PROJECT_ENVIRONMENT="$HERMES_INSTALL_DIR/venv" uv sync --extra all --extra voice --extra edge-tts --extra nemo-relay --locked
              )
              exec "$HERMES_INSTALL_DIR/venv/bin/hermes" --version
            '';
            executable = true;
            force = true;
          };
        };

      environment.systemPackages = [
        scriptPkgs.beads
      ];
    };
} args
