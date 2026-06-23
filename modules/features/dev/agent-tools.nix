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
      claudeSettingsBase = builtins.fromJSON (
        builtins.readFile (inputs.self + "/dots/claude/settings.json")
      );
      claudeSettingsFile = jsonFormat.generate "claude-settings.json" claudeSettingsBase;
      sharedSkillNames = [
        "adversarial-loop"
        "agent-orchestration"
        "analyze"
        "assured-close"
        "desktop-control-plane"
        "enhance"
        "evidence-harness"
        "greedy-batching"
        "history-cleanup"
        "lynchpin"
        "meta"
        "recap"
        "swarm"
      ];
      sharedSkillFarm = pkgs.linkFarm "sinnix-shared-agent-skills" (
        map (name: {
          inherit name;
          path = inputs.self + "/dots/_ai/skills/${name}";
        }) sharedSkillNames
      );
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
          mcpConfigName ? "mcp",
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

            ${agentScopePrelude}

            mcp_args=()
            MCP_CONFIG="$HOME/.config/claude/${mcpConfigName}.json"
            if [ -r "$MCP_CONFIG" ]; then
              mcp_args=(--mcp-config "$MCP_CONFIG" --strict-mcp-config)
            fi

            claude_args=(
              "''${mcp_args[@]}"
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
          profile,
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

            codex_args=(--profile ${lib.escapeShellArg profile})

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
              claude = "~/.local/bin/claude";
              claude-lean = "~/.local/bin/claude-lean";
              claude-browser = "~/.local/bin/claude-browser";
              codex = "~/.local/bin/codex";
              codex-lean = "~/.local/bin/codex-lean";
              codex-browser = "~/.local/bin/codex-browser";
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
            "claude/mcp-lean.json".source = claudeLeanMcpConfigFile;
            "claude/mcp-browser.json".source = claudeBrowserMcpConfigFile;
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
            "claude/skills" = {
              source = sharedSkillFarm;
              force = true;
            };
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
          home.file.".local/bin/claude-lean" = mkClaudeCodeWrapper {
            mcpConfigName = "mcp-lean";
          };
          home.file.".local/bin/claude-browser" = mkClaudeCodeWrapper {
            mcpConfigName = "mcp-browser";
          };

          home.file.".local/bin/codex" = mkCodexWrapper { profile = "full"; };
          home.file.".local/bin/codex-lean" = mkCodexWrapper { profile = "lean"; };
          home.file.".local/bin/codex-browser" = mkCodexWrapper { profile = "browser"; };

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
