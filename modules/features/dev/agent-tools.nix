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
            scriptPkgs.render-agents
            scriptPkgs.normalize-agent-projects
            scriptPkgs.verify-agent-topology
          ];

          programs.zsh = {
            shellAliases = {
              cl = "~/.local/bin/claude";
              claude = "~/.local/bin/claude";
              ct = "~/.local/bin/claude-team";
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
            "claude/settings.json".source = mkDotsFile "/claude/settings.json";
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

          home.file.".local/bin/claude" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              CLAUDE_BIN="${aiTools.claude-code}/bin/claude"
              REALM_DIR="${sinnixCfg.paths.realmRoot}"
              HOME_DIR="${config.home.homeDirectory}"

              if [ -d "$REALM_DIR" ]; then
                exec "$CLAUDE_BIN" --add-dir "$REALM_DIR" "$HOME_DIR" "$@"
              else
                exec "$CLAUDE_BIN" "$HOME_DIR" "$@"
              fi
            '';
            executable = true;
          };

          home.file.".local/bin/claude-team" = {
            text = ''
              #!/usr/bin/env bash
              # Launch Claude Code inside tmux for agent team split panes.
              # If already in tmux, just runs claude directly (auto-detected).
              set -euo pipefail

              CLAUDE="$HOME/.local/bin/claude"

              if [ -n "''${TMUX:-}" ]; then
                exec "$CLAUDE" "$@"
              fi

              # Outside tmux — start a named session running claude
              printf -v claude_cmd '%q ' "$CLAUDE" "$@"
              exec tmux new-session -s ct "$claude_cmd"
            '';
            executable = true;
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

              exec "$FORGE_BIN" "$@"
            '';
            executable = true;
            force = true;
          };

          home.file.".local/bin/codex" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              CODEX_BIN="${aiTools.codex}/bin/codex"

              exec "$CODEX_BIN" "$@"
            '';
            executable = true;
          };

          home.file.".local/bin/gemini" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              GEMINI_BIN="${aiTools.gemini-cli}/bin/gemini"

              exec "$GEMINI_BIN" "$@"
            '';
            executable = true;
          };
        };
    };
} args
