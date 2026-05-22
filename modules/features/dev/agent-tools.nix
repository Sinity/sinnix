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
      aiTools = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system};

      # Pin claude-code ahead of upstream llm-agents when it lags behind.
      # Mirror of the override in languages.nix — remove both once upstream catches up.
      claude-code = aiTools.claude-code.overrideAttrs (old: rec {
        version = "2.1.111";
        src = pkgs.fetchurl {
          url = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/${version}/linux-x64/claude";
          hash = "sha256-XU35cAQLD4OqxDSuVAtAkSakd4o3noybTHk1YOO/oGA=";
        };
      });

      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      forgePkg = aiTools.forge;
      forgeZshPlugin = pkgs.runCommandLocal "forge-zsh-plugin.zsh" { } ''
        export HOME="$TMPDIR"
        ${lib.getExe forgePkg} zsh plugin > "$out"
      '';
      forgeZshTheme = pkgs.runCommandLocal "forge-zsh-theme.zsh" { } ''
        export HOME="$TMPDIR"
        ${lib.getExe forgePkg} zsh theme > "$out"
      '';
      sinnixCfg = config.sinnix;

      jsonFormat = pkgs.formats.json { };
      mcpRegistry = import ../../lib/mcp-registry.nix { inherit lib; };
      claudeMcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
        mcpRegistry.selectClientServers "claude"
      );
      # Dedicated registry-driven MCP config consumed via `claude --mcp-config`.
      # Claude Code 2.x does NOT read `mcpServers` from settings.json — only
      # `.mcp.json` (project), `~/.claude.json` (user, managed by `claude mcp add`),
      # or `--mcp-config <file>` recognise stdio servers. This file is the
      # registry's connection point.
      claudeMcpConfigFile = jsonFormat.generate "claude-mcp.json" {
        mcpServers = claudeMcpServers;
      };
      claudeSettingsBase = builtins.fromJSON (
        builtins.readFile (inputs.self + "/dots/claude/settings.json")
      );
      claudeSettingsFile = jsonFormat.generate "claude-settings.json" claudeSettingsBase;
      agentScopePrelude = ''
        run_agent_scoped() {
          if [[ -z "''${SINNIX_AGENT_SCOPED:-}" ]]; then
            scope_bin="${scriptPkgs.sinnix-scope}/bin/sinnix-scope"
            if [[ ! -x "$scope_bin" ]]; then
              scope_bin="$(command -v sinnix-scope 2>/dev/null || true)"
            fi
            if [[ -n "$scope_bin" && -x "$scope_bin" ]]; then
              exec "$scope_bin" agent -- ${pkgs.coreutils}/bin/env SINNIX_AGENT_SCOPED=1 "$@"
            fi
          fi

          exec "$@"
        }
      '';
      mkClaudeCodeWrapper =
        {
          useMcp ? true,
          extraEnv ? "",
          extraArgs ? [ ],
        }:
        {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            CLAUDE_BIN="${claude-code}/bin/claude"
            REALM_DIR="${sinnixCfg.paths.realmRoot}"
            HOME_DIR="/home/${user}"
            MCP_CONFIG="$HOME/.config/claude/mcp.json"

            ${extraEnv}
            ${agentScopePrelude}

            mcp_args=()
            ${lib.optionalString useMcp ''
              if [ -r "$MCP_CONFIG" ]; then
                mcp_args=(--mcp-config "$MCP_CONFIG" --strict-mcp-config)
              fi
            ''}
            wrapper_args=(${lib.concatStringsSep " " (map lib.escapeShellArg extraArgs)})

            if [ -d "$REALM_DIR" ]; then
              run_agent_scoped "$CLAUDE_BIN" "''${mcp_args[@]}" --add-dir "$REALM_DIR" "$HOME_DIR" "''${wrapper_args[@]}" "$@"
            else
              run_agent_scoped "$CLAUDE_BIN" "''${mcp_args[@]}" --add-dir "$HOME_DIR" "''${wrapper_args[@]}" "$@"
            fi
          '';
          executable = true;
          force = true;
        };
      mkCodexProfileWrapper = profile: {
        text = ''
          #!/usr/bin/env bash
          set -euo pipefail

          CODEX_BIN="${aiTools.codex}/bin/codex"

          ${agentScopePrelude}

          run_agent_scoped "$CODEX_BIN" --profile ${lib.escapeShellArg profile} "$@"
        '';
        executable = true;
        force = true;
      };
    in
    {
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
          {
            directory = "forge";
            mode = "0700";
          }
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
          home.sessionVariables = {
            FORGE_EDITOR = "nvim";
            FORGE_BIN = "\${HOME}/.local/bin/forge";
          };

          home.packages = [
            scriptPkgs.sinnix-scope
            scriptPkgs.render-agents
            scriptPkgs.normalize-agent-projects
            scriptPkgs.verify-agent-topology

            # Upstream agent ecosystem tools. Sinnix owns projection/wrappers;
            # llm-agents.nix owns fast-moving package supply.
            aiTools.agent-browser
            aiTools.agent-deck
            aiTools.agentsview
            aiTools.beads-rust
            aiTools.beads-viewer
            aiTools.claude-agent-acp
            aiTools.codex-acp
            aiTools.herdr
            aiTools.opencode
            aiTools.skills
          ];

          programs.zsh = {
            shellAliases = {
              cl = "~/.local/bin/claude";
              claude = "~/.local/bin/claude";
              claude-lite = "~/.local/bin/claude-lite";
              claude-opus = "~/.local/bin/claude-opus";
              claude-sonnet = "~/.local/bin/claude-sonnet";
              ct = "~/.local/bin/claude-team";
              codex-deep = "~/.local/bin/codex-deep";
              codex-fast = "~/.local/bin/codex-fast";
              codex-max = "~/.local/bin/codex-max";
              codex-spark = "~/.local/bin/codex-spark";
              codex-spark-xhigh = "~/.local/bin/codex-spark-xhigh";
              deepseek = "~/.local/bin/deepseek";
              gemini = "~/.local/bin/gemini";
            };
            initContent = lib.mkAfter ''
              export FORGE_BIN="$HOME/.local/bin/forge"
              if [ -x "$FORGE_BIN" ]; then
                source ${forgeZshPlugin}
                source ${forgeZshTheme}
                bindkey -M viins '^M' forge-accept-line
                bindkey -M viins '^J' forge-accept-line
                bindkey -M viins '^I' forge-completion
              fi
            '';
          };

          xdg.configFile = {
            "claude/hooks/pretooluse-bash.sh".source = mkDotsFile "/claude/hooks/pretooluse-bash.sh";
            "claude/hooks/sessionstart-polylogue-recall.sh".source =
              mkDotsFile "/claude/hooks/sessionstart-polylogue-recall.sh";
            # Static settings.json fragment (permissions, hooks, plugins). MCP
            # servers are NOT here because Claude Code 2.x ignores any
            # `mcpServers` block in settings.json — they're delivered via
            # `--mcp-config` from the wrapper instead (see ./claude-mcp.json).
            "claude/settings.json".source = claudeSettingsFile;
            # Registry-driven MCP config consumed by the claude wrapper.
            "claude/mcp.json".source = claudeMcpConfigFile;
            "claude/CLAUDE.md".source = mkDotsFile "/claude/CLAUDE.md";
            "claude/world-model" = {
              source = mkDotsFile "/claude/world-model";
              force = true;
              recursive = true;
            };
            "claude/operational" = {
              source = mkDotsFile "/claude/operational";
              force = true;
              recursive = true;
            };
            # Single symlink → _ai/skills (shared skill source with real dirs).
            # No recursive — one symlink for the whole directory.
            "claude/skills".source = mkDotsFile "/_ai/skills";
          };

          home.activation.claudeSymlink = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            ln -sfn .config/claude $HOME/.claude
          '';
          home.activation.renderGlobalCodexAgents = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p "$HOME/.codex"
            if [ -f "$HOME/.config/claude/CLAUDE.md" ]; then
              ${scriptPkgs.render-agents}/bin/render-agents \
                --input "$HOME/.config/claude/CLAUDE.md" \
                --output "$HOME/.codex/AGENTS.md"
            fi
          '';
          home.activation.renderGlobalGeminiAgents = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p "$HOME/.gemini"
            if [ -f "$HOME/.config/claude/CLAUDE.md" ]; then
              ${scriptPkgs.render-agents}/bin/render-agents \
                --input "$HOME/.config/claude/CLAUDE.md" \
                --output "$HOME/.gemini/GEMINI.md"
            fi
          '';
          home.activation.renderGlobalForgeAgents = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p \
              "$HOME/forge" \
              "$HOME/forge/agents" \
              "$HOME/forge/commands" \
              "$HOME/forge/logs/requests"
            if [ -f "$HOME/.config/claude/CLAUDE.md" ]; then
              ${scriptPkgs.render-agents}/bin/render-agents \
                --input "$HOME/.config/claude/CLAUDE.md" \
                --output "$HOME/forge/AGENTS.md"
            fi
          '';
          home.activation.forgeSkillsMigration = lib.hm.dag.entryBefore [ "checkLinkTargets" ] ''
            target="$HOME/forge/skills"
            backup="$HOME/forge/skills.pre-home-manager-backup"

            if [ -d "$target" ] && [ ! -L "$target" ]; then
              if find "$target" -mindepth 1 -print -quit | grep -q .; then
                if [ -e "$backup" ]; then
                  echo "Refusing to overwrite existing $backup while migrating $target" >&2
                  exit 1
                fi
                mv "$target" "$backup"
              else
                rmdir "$target"
              fi
            fi
          '';

          home.file.".local/bin/claude" = mkClaudeCodeWrapper { };

          home.file.".local/bin/claude-opus" = mkClaudeCodeWrapper {
            extraArgs = [
              "--model"
              "opus"
              "--effort"
              "high"
            ];
          };

          home.file.".local/bin/claude-sonnet" = mkClaudeCodeWrapper {
            extraArgs = [
              "--model"
              "sonnet"
              "--effort"
              "medium"
            ];
          };

          home.file.".local/bin/claude-lite" = mkClaudeCodeWrapper {
            useMcp = false;
            extraArgs = [ "--bare" ];
          };

          home.file.".local/bin/deepseek" = mkClaudeCodeWrapper {
            extraEnv = ''
              DEEPSEEK_KEY_FILE="/run/agenix/deepseek-api-key"
              if [ ! -r "$DEEPSEEK_KEY_FILE" ]; then
                echo "deepseek: cannot read $DEEPSEEK_KEY_FILE" >&2
                exit 1
              fi

              export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
              export ANTHROPIC_AUTH_TOKEN="$(<"$DEEPSEEK_KEY_FILE")"
              DEEPSEEK_MODEL="deepseek-v4-pro[1m]"
              export ANTHROPIC_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_OPUS_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_SONNET_MODEL="$DEEPSEEK_MODEL"
              export ANTHROPIC_DEFAULT_HAIKU_MODEL="$DEEPSEEK_MODEL"
              export CLAUDE_CODE_SUBAGENT_MODEL="$DEEPSEEK_MODEL"
              export CLAUDE_CODE_EFFORT_LEVEL="max"
            '';
          };

          home.file.".local/bin/claude-team" = {
            text = ''
              #!/usr/bin/env bash
              # Launch a selected Claude Code wrapper inside tmux for agent team split panes.
              # Override CLAUDE_WRAPPER=claude-opus/claude-sonnet/deepseek when desired.
              set -euo pipefail

              CLAUDE="$HOME/.local/bin/''${CLAUDE_WRAPPER:-claude}"

              if [ -n "''${TMUX:-}" ]; then
                exec "$CLAUDE" "$@"
              fi

              printf -v claude_cmd '%q ' "$CLAUDE" "$@"
              exec tmux new-session -s ct "$claude_cmd"
            '';
            executable = true;
            force = true;
          };

          home.file."forge/.forge.toml" = {
            source = mkDotsFile "/forge/.forge.toml";
            force = true;
          };
          # Shared skills should stay a single directory symlink; recursively
          # materializing the tree invites junk self-links and duplicate state.
          home.file."forge/skills".source = mkDotsFile "/_ai/skills";

          home.file.".local/bin/forge" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              FORGE_BIN="${forgePkg}/bin/forge"

              ${agentScopePrelude}

              run_agent_scoped "$FORGE_BIN" "$@"
            '';
            executable = true;
            force = true;
          };

          home.file.".local/bin/codex" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              CODEX_BIN="${aiTools.codex}/bin/codex"

              ${agentScopePrelude}

              run_agent_scoped "$CODEX_BIN" "$@"
            '';
            executable = true;
            force = true;
          };

          home.file.".local/bin/codex-fast" = mkCodexProfileWrapper "fast";
          home.file.".local/bin/codex-deep" = mkCodexProfileWrapper "deep";
          home.file.".local/bin/codex-max" = mkCodexProfileWrapper "max";
          home.file.".local/bin/codex-spark" = mkCodexProfileWrapper "spark_medium";
          home.file.".local/bin/codex-spark-xhigh" = mkCodexProfileWrapper "spark_xhigh";

          home.file.".local/bin/gemini" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              GEMINI_BIN="${aiTools.gemini-cli}/bin/gemini"

              ${agentScopePrelude}

              run_agent_scoped "$GEMINI_BIN" "$@"
            '';
            executable = true;
            force = true;
          };
        };
    };
} args
