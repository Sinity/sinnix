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
        ])
      );

      # Shared npm bootstrap prelude — delegates state-dir setup, first-run npm
      # install, and launcher regeneration to the packaged
      # sinnix-agent-npm-bootstrap script (scripts/sinnix-agent-npm-bootstrap).
      # The long-lived agent process launches directly via the generated
      # launch.sh, not through buildFHSEnv/bubblewrap, so sudo and other
      # privileged helpers do not inherit no_new_privileges. `STATE` is
      # recomputed here (not exported by the bootstrap subprocess) because the
      # wrapper needs it below for the final agent-scope-exec/launch call.
      mkNpmBootstrap =
        {
          stateDir,
          npmPackage,
          binaryName,
        }:
        ''
          STATE="$HOME/.local/state/${stateDir}"
          ${scriptPkgs.sinnix-agent-npm-bootstrap}/bin/sinnix-agent-npm-bootstrap \
            ${lib.escapeShellArg stateDir} \
            ${lib.escapeShellArg npmPackage} \
            ${lib.escapeShellArg binaryName} \
            ${lib.escapeShellArg agentRuntimePath}
        '';

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
      sharedSkillNames = import ../../../flake/data/shared-agent-skills.nix;
      sharedSkillFarm = pkgs.linkFarm "sinnix-shared-agent-skills" (
        map (name: {
          inherit name;
          path = inputs.self + "/dots/_ai/skills/${name}";
        }) sharedSkillNames
      );
      # Runs the given launcher under sinnix-scope's agent slice unless already
      # scoped (see scripts/sinnix-agent-scope-exec).
      agentScopeExec = "${scriptPkgs.sinnix-agent-scope-exec}/bin/sinnix-agent-scope-exec";
      mkClaudeCodeWrapper =
        {
          mcpConfigName ? "mcp",
          profile ?
            if mcpConfigName == "mcp-lean" then
              "lean"
            else if mcpConfigName == "mcp-browser" then
              "browser"
            else
              "full",
          # Extra shell injected after the npm bootstrap and before launch — used
          # to point Claude Code at a non-Anthropic backend (DeepSeek, local
          # gateway) via ANTHROPIC_BASE_URL / ANTHROPIC_MODEL / auth env vars.
          extraEnv ? "",
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

            export SINNIX_CLAUDE_PROFILE=${lib.escapeShellArg profile}
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

            exec ${agentScopeExec} "$STATE/launch.sh" "''${claude_args[@]}" "$@"
          '';
          executable = true;
          force = true;
        };
      mkCodexWrapper =
        {
          profile,
          # Extra shell injected after the npm bootstrap — used to export the
          # provider API key the layered `<profile>.config.toml` expects.
          extraEnv ? "",
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

            ${extraEnv}

            export SINNIX_CODEX_PROFILE=${lib.escapeShellArg profile}
            codex_args=(--profile ${lib.escapeShellArg profile})

            exec ${agentScopeExec} "$STATE/launch.sh" "''${codex_args[@]}" "$@"
          '';
          executable = true;
          force = true;
        };
      # Env-only prelude for Hermes wrappers. PATH/HERMES_HOME/HERMES_INSTALL_DIR
      # must be exported here (not in a subprocess) because the final `exec` of
      # the hermes binary below needs to inherit them. The actual clone/sync/
      # scaffold bootstrap logic lives in scripts/sinnix-ensure-hermes, which
      # runs as a subprocess relying on this already-exported PATH/env.
      hermesBootstrap = ''
        export HERMES_HOME="''${HERMES_HOME:-$HOME/.hermes}"
        export HERMES_INSTALL_DIR="''${HERMES_INSTALL_DIR:-$HERMES_HOME/hermes-agent}"
        export PATH="${hermesRuntimePath}:$PATH"
        export UV_NO_CONFIG=1
        export UV_PYTHON="${pkgs.python313}/bin/python3"
      '';
      ensureHermes = "${scriptPkgs.sinnix-ensure-hermes}/bin/sinnix-ensure-hermes";
      hermesConfigureLocal = "${scriptPkgs.sinnix-hermes-configure-local}/bin/sinnix-hermes-configure-local";
      mkHermesWrapper =
        {
          entrypoint ? "hermes",
          extraPrelude ? "",
        }:
        {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            ${hermesBootstrap}

            ${ensureHermes}
            ${extraPrelude}

            exec "$HERMES_INSTALL_DIR/venv/bin/${entrypoint}" "$@"
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
            scriptPkgs.chatgpt-share-export
            scriptPkgs.verify-agent-topology
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
              hermes = "~/.local/bin/hermes";
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
              text = builtins.readFile ../../../dots/claude/hooks/sessionstart-sinex-recall.sh;
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
          # (generated in mcp-servers.nix) carries the model + model_provider +
          # full MCP table; the wrapper only supplies the provider API key env.
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

          home.file.".local/bin/hermes" = mkHermesWrapper { };
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
                UV_PROJECT_ENVIRONMENT="$HERMES_INSTALL_DIR/venv" uv sync --extra all --locked
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
