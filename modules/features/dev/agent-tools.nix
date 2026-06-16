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
      agentRuntimePath = lib.makeBinPath (
        with pkgs;
        [
          nodejs_22
          git
          bash
          gnutar
          gzip
          which
          coreutils
          gcc
        ]
      );

      # Shared npm bootstrap prelude — generates state-dir setup, first-run
      # npm install, and a regenerated launcher script. The long-lived agent
      # process launches directly, not through buildFHSEnv/bubblewrap, so sudo
      # and other privileged helpers do not inherit no_new_privileges.
      mkNpmBootstrap =
        {
          stateDir,
          npmPackage,
          binaryName,
        }:
        ''
          STATE="$HOME/.local/state/${stateDir}"
          export npm_config_prefix="$STATE/npm"
          export PATH="${agentRuntimePath}:$STATE/npm/bin:$PATH"
          mkdir -p "$STATE/npm"

          if [ ! -x "$STATE/npm/bin/${binaryName}" ]; then
            echo "${binaryName}: bootstrapping (npm install -g ${npmPackage})..." >&2
            npm install -g ${npmPackage}
          fi

          cat > "$STATE/launch.sh" <<'LAUNCHER'
        ''
        + ''
          #!/usr/bin/env bash
          PATH="${agentRuntimePath}:$HOME/.local/state/${stateDir}/npm/bin:$PATH"
          exec ${binaryName} "$@"
        ''
        + ''
          LAUNCHER
          chmod +x "$STATE/launch.sh"
        '';

      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      sinnixCfg = config.sinnix;

      jsonFormat = pkgs.formats.json { };
      inherit (helpers.data) mcpRegistry;
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

            ${mkNpmBootstrap {
              stateDir = "claude-code";
              npmPackage = "@anthropic-ai/claude-code";
              binaryName = "claude";
            }}

            ${extraEnv}
            ${agentScopePrelude}

            mcp_args=()
            ${lib.optionalString useMcp ''
              if [ -r "$HOME/.config/claude/mcp.json" ]; then
                mcp_args=(--mcp-config "$HOME/.config/claude/mcp.json" --strict-mcp-config)
              fi
            ''}
            wrapper_args=(${lib.concatStringsSep " " (map lib.escapeShellArg extraArgs)})

            claude_args=(
              "''${mcp_args[@]}"
              "''${wrapper_args[@]}"
            )
            if [ -d "${sinnixCfg.paths.realmRoot}" ]; then
              claude_args+=(--add-dir "${sinnixCfg.paths.realmRoot}" "/home/${user}")
            else
              claude_args+=(--add-dir "/home/${user}")
            fi

            run_agent_scoped "$STATE/launch.sh" "''${claude_args[@]}" "$@"
          '';
          executable = true;
          force = true;
        };
      mkCodexWrapper =
        {
          profile ? null,
        }:
        {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            ${mkNpmBootstrap {
              stateDir = "codex";
              npmPackage = "@openai/codex";
              binaryName = "codex";
            }}

            ${agentScopePrelude}

            codex_args=()
            ${lib.optionalString (profile != null) ''
              codex_args+=(--profile ${lib.escapeShellArg profile})
            ''}

            run_agent_scoped "$STATE/launch.sh" "''${codex_args[@]}" "$@"
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
          # npm installs survive impermanence cold boots so agents do not
          # re-download on every activation.
          ".local/state/claude-code"
          ".local/state/codex"
          ".local/state/gemini"
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
            scriptPkgs.sinnix-scope
            scriptPkgs.chatgpt-share-export
            scriptPkgs.render-agents
            scriptPkgs.normalize-agent-projects
            scriptPkgs.verify-agent-topology
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

          home.file.".local/bin/codex" = mkCodexWrapper { };
          home.file.".local/bin/codex-fast" = mkCodexWrapper { profile = "fast"; };
          home.file.".local/bin/codex-deep" = mkCodexWrapper { profile = "deep"; };
          home.file.".local/bin/codex-max" = mkCodexWrapper { profile = "max"; };
          home.file.".local/bin/codex-spark" = mkCodexWrapper { profile = "spark_medium"; };
          home.file.".local/bin/codex-spark-xhigh" = mkCodexWrapper { profile = "spark_xhigh"; };

          home.file.".local/bin/gemini" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              ${mkNpmBootstrap {
                stateDir = "gemini";
                npmPackage = "@google/gemini-cli";
                binaryName = "gemini";
              }}

              ${agentScopePrelude}

              run_agent_scoped "$STATE/launch.sh" "$@"
            '';
            executable = true;
            force = true;
          };
        };
    };
} args
