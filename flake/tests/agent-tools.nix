# Agent CLI wrapper / MCP profile runtime checks (Claude, Codex, Gemini).
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      runtimeDefaults = import ../data/runtime-defaults.nix { inherit lib; };
      agentScopeProperties = runtimeDefaults.commandClasses.agent.systemdProperties;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        evalTestSpec
        mkFeatureTest
        mkHmRuntimeCheck
        ;

      devAgentToolsRuntimeSpec = mkFeatureTest {
        name = "dev-agent-tools-runtime";
        feature = "sinnix.features.dev.agentTools.enable";
        extraModules = [
          (_: {
            sinnix.features.dev.shell.enable = true;
            sinnix.features.dev.mcp-servers.enable = true;
          })
        ];
        assertions =
          config:
          let
            hm = config.home-manager.users.${config.sinnix.user.name};
            activationText = hm.home.activation.claudeSymlink.data or "";
          in
          [
            {
              assertion = (agentScopeProperties.MemoryHigh or null) == "8G";
              message = "Each transient agent scope must begin reclaim pressure at 8G.";
            }
            {
              assertion = (agentScopeProperties.MemoryMax or null) == "12G";
              message = "Each transient agent scope must stop before exceeding 12G.";
            }
            {
              assertion = !(agentScopeProperties ? OOMScoreAdjust);
              message = "OOMScoreAdjust is not valid on transient scope units.";
            }
            {
              assertion = !(agentScopeProperties ? MemorySwapMax);
              message = "Agent containment must not restore brittle per-scope swap ceilings.";
            }
            {
              assertion = !(hm.xdg.configFile ? "claude/settings.json");
              message = "Claude settings.json must not be managed through Home Manager xdg.configFile.";
            }
            {
              assertion = lib.hasInfix "${config.sinnix.paths.dotsRoot}/claude/settings.json" activationText;
              message = "Claude settings.json must be linked directly to dots during activation.";
            }
          ];
      };
      agentToolsFixture = {
        spec = devAgentToolsRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.expect
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.python3
          pkgs.zsh
        ];
        homeFiles = [
          ".gemini/settings.json"
          ".gemini/config/mcp_config.json"
          ".gemini/config/skills"
          ".gemini/config/AGENTS.md"
          ".local/bin/claude-full"
          ".local/bin/claude-lean"
          ".local/bin/claude-browser"
          ".local/bin/claude-deepseek"
          ".local/bin/claude-local"
          ".local/bin/codex"
          ".local/bin/codex-lean"
          ".local/bin/codex-full"
          ".local/bin/codex-browser"
          ".local/bin/codex-deepseek"
          ".local/bin/codex-local"
          ".local/bin/gemini"
          ".local/bin/agy-sinnix"
          ".local/bin/hermes"
          ".local/bin/hermes-research"
          ".local/bin/hermes-orchestrate"
          ".local/bin/hermes-mirror"
          ".local/bin/codebase-memory-mcp"
          ".local/bin/serena"
          ".local/bin/serena-hooks"
          ".local/bin/bd-prime-if-present"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-chrome-devtools"
          ".local/bin/mcp-chrome-devtools-private"
          ".local/bin/mcp-chrome-devtools-private-visible"
          ".local/bin/mcp-polylogue"
          ".local/bin/mcp-sinex"
          ".local/bin/sinnix-mcp-sweep"
          ".local/bin/sinnix-agent-status"
          ".local/bin/sinnix-chrome-control"
          ".local/bin/sinnix-hypr-control"
          ".local/bin/sinnix-keyboard-control"
          ".local/bin/sinnix-kitty-control"
          ".local/bin/sinnix-screenshot-control"
          ".config/hermes/skills"
        ];
        xdgConfigFiles = [
          "claude/mcp.json"
          "claude/mcp-lean.json"
          "claude/mcp-browser.json"
        ];
        useHmZshrc = true;
        zshrcPreamble = ''
          autoload -Uz compinit
          compinit
        '';
        setup = ''
          export PATH="$HOME/.local/bin:${
            lib.makeBinPath [
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.zsh
            ]
          }:$PATH"
          export SHELL="${pkgs.zsh}/bin/zsh"
          export TERM="xterm-kitty"
          export TERM_PROGRAM="kitty"
          export TERM_PROGRAM_VERSION="test"
          export ZDOTDIR="$HOME"
        '';
      };
      agentToolsRuntimeConfig = (evalTestSpec system devAgentToolsRuntimeSpec).config;
      agentToolsCodexConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexConfigSource;
      agentToolsCodexFullConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexFullConfigSource;
      agentToolsCodexLeanConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexLeanConfigSource;
      agentToolsCodexEvidenceConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexEvidenceConfigSource;
      agentToolsCodexBrowserConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexBrowserConfigSource;
      agentToolsCodexDeepseekConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexDeepseekConfigSource;
      agentToolsCodexLocalConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexLocalConfigSource;
      agentToolsCodexHooksSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexHooksSource;
      agentToolsAntigravityMcpConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.antigravityMcpConfigSource;
      agentToolsHermesConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.agentTools.hermesConfigSource;
      agentToolsHermesProfileConfigSources =
        agentToolsRuntimeConfig.sinnix.features.dev.agentTools.hermesProfileConfigSources;

      agentResourcePolicy =
        let
          avoidPattern = runtimeDefaults.earlyoomEmergencyAvoidPattern;
          forbiddenAvoidTokens = [
            "bash"
            "chrome"
            "chromium"
            "claude"
            "codex"
            "electron"
            "firefox"
            "node"
            "python"
            "zsh"
          ];
        in
        assert lib.assertMsg (
          (agentScopeProperties.MemoryHigh or null) == "8G"
        ) "transient agent scopes must begin reclaim pressure at 8G";
        assert lib.assertMsg (
          (agentScopeProperties.MemoryMax or null) == "12G"
        ) "transient agent scopes must stop before exceeding 12G";
        assert lib.assertMsg (
          !(agentScopeProperties ? OOMScoreAdjust)
        ) "OOMScoreAdjust is not valid on transient scope units";
        assert lib.assertMsg (
          !(agentScopeProperties ? MemorySwapMax)
        ) "agent containment must not restore brittle per-scope swap ceilings";
        assert lib.assertMsg (lib.hasInfix "start-hyprland" avoidPattern)
          "the earlyoom fallback must protect the lowercase UWSM session launcher";
        assert lib.assertMsg (lib.all (token: !(lib.hasInfix token avoidPattern))
          forbiddenAvoidTokens
        ) "the earlyoom fallback must not exempt agents, browsers, runtimes, or generic shells";
        pkgs.runCommand "sinnix-agent-resource-policy-check" { } ''
          touch "$out"
        '';

      agentNpmBootstrapRecovery =
        pkgs.runCommand "sinnix-agent-npm-bootstrap-recovery-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.util-linux
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            state="$HOME/.local/state/fake-agent/npm"
            package_parent="$state/lib/node_modules/@example"
            mkdir -p \
              "$package_parent/.fake-cli-AbCd1234" \
              "$package_parent/..fake-cli-ZyXw9876" \
              "$state/bin" \
              "$TMPDIR/bin"
            ln -s /missing "$state/bin/.fakeagent-Qwer1234"

            cat > "$TMPDIR/bin/npm" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail
            package_parent="$npm_config_prefix/lib/node_modules/@example"
            test ! -e "$package_parent/.fake-cli-AbCd1234"
            test ! -e "$package_parent/..fake-cli-ZyXw9876"
            test ! -L "$npm_config_prefix/bin/.fakeagent-Qwer1234"

            exec 8>>"$HOME/npm-invocations.lock"
            flock 8
            count=0
            if [ -f "$HOME/npm-invocations" ]; then
              count=$(cat "$HOME/npm-invocations")
            fi
            printf '%s\n' "$((count + 1))" > "$HOME/npm-invocations"
            sleep 0.2

            mkdir -p "$npm_config_prefix/bin"
            cat > "$npm_config_prefix/bin/fakeagent" <<'AGENT'
            #!${pkgs.bash}/bin/bash
            printf 'fakeagent 1.0\n'
            AGENT
            chmod +x "$npm_config_prefix/bin/fakeagent"
            EOF
            chmod +x "$TMPDIR/bin/npm"

            runtime_path="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.bash
                pkgs.coreutils
                pkgs.util-linux
              ]
            }"
            bootstrap=${../../scripts/sinnix-agent-npm-bootstrap}
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path" &
            first=$!
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path" &
            second=$!
            wait "$first"
            wait "$second"

            test "$(cat "$HOME/npm-invocations")" = 1
            test ! -e "$package_parent/.fake-cli-AbCd1234"
            test ! -e "$package_parent/..fake-cli-ZyXw9876"
            test ! -L "$state/bin/.fakeagent-Qwer1234"
            test -x "$state/bin/fakeagent"

            # A healthy canonical binary must bypass cleanup and npm entirely.
            mkdir "$package_parent/.fake-cli-Keep1234"
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path"
            test "$(cat "$HOME/npm-invocations")" = 1
            test -d "$package_parent/.fake-cli-Keep1234"
            test "$(${pkgs.bash}/bin/bash "$HOME/.local/state/fake-agent/launch.sh" --version)" = "fakeagent 1.0"
            touch "$out"
          '';

      devAgentToolsRuntime = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-runtime-check";
          nativeBuildInputs = builtins.filter (pkg: pkg != pkgs.expect) agentToolsFixture.nativeBuildInputs;
          setup = agentToolsFixture.setup + ''
            mkdir -p "$HOME/.codex"
            cp ${agentToolsCodexConfigSource} "$HOME/.codex/config.toml"
            cp ${agentToolsCodexFullConfigSource} "$HOME/.codex/full.config.toml"
            cp ${agentToolsCodexLeanConfigSource} "$HOME/.codex/lean.config.toml"
            cp ${agentToolsCodexEvidenceConfigSource} "$HOME/.codex/evidence.config.toml"
            cp ${agentToolsCodexBrowserConfigSource} "$HOME/.codex/browser.config.toml"
            cp ${agentToolsCodexDeepseekConfigSource} "$HOME/.codex/deepseek.config.toml"
            cp ${agentToolsCodexLocalConfigSource} "$HOME/.codex/local.config.toml"
            cp ${agentToolsCodexHooksSource} "$HOME/.codex/hooks.json"
            mkdir -p "$HOME/.gemini/config"
            cp ${agentToolsAntigravityMcpConfigSource} "$HOME/.gemini/config/mcp_config.json"
            mkdir -p "$HOME/.hermes"
            cp ${agentToolsHermesConfigSource} "$HOME/.hermes/config.yaml"
            for profile in research orchestrate mirror; do
              mkdir -p "$HOME/.hermes/profiles/$profile"
              ln -s ../../auth.json "$HOME/.hermes/profiles/$profile/auth.json"
              ln -s ../../.env "$HOME/.hermes/profiles/$profile/.env"
              ln -s ../../SOUL.md "$HOME/.hermes/profiles/$profile/SOUL.md"
            done
            cp ${agentToolsHermesProfileConfigSources.research} "$HOME/.hermes/profiles/research/config.yaml"
            cp ${agentToolsHermesProfileConfigSources.orchestrate} "$HOME/.hermes/profiles/orchestrate/config.yaml"
            cp ${agentToolsHermesProfileConfigSources.mirror} "$HOME/.hermes/profiles/mirror/config.yaml"
            chmod 600 "$HOME/.hermes/config.yaml" "$HOME/.hermes/profiles/research/config.yaml" \
              "$HOME/.hermes/profiles/orchestrate/config.yaml" "$HOME/.hermes/profiles/mirror/config.yaml"
            chmod 644 "$HOME/.codex/config.toml"
            chmod 644 "$HOME/.codex/full.config.toml"
            chmod 644 "$HOME/.codex/lean.config.toml"
            chmod 644 "$HOME/.codex/evidence.config.toml"
            chmod 644 "$HOME/.codex/browser.config.toml"
            chmod 644 "$HOME/.codex/deepseek.config.toml"
            chmod 644 "$HOME/.codex/local.config.toml"
            chmod 644 "$HOME/.codex/hooks.json"
          '';
          script = ''
            trap 'echo "dev-agent-tools-runtime failed at line $LINENO" >&2' ERR

            test -f "$HOME/.codex/config.toml"
            test ! -L "$HOME/.codex/config.toml"
            test ! -L "$HOME/.codex/hooks.json"
            test -f "$HOME/.gemini/settings.json"
            test -f "$HOME/.gemini/config/mcp_config.json"
            test -L "$HOME/.gemini/config/skills"
            test -L "$HOME/.gemini/config/AGENTS.md"
            test -L "$HOME/.config/claude/mcp.json"
            test -L "$HOME/.config/hermes/skills"
            python3 - "$HOME/.hermes/config.yaml" <<'PYCODE'
            import pathlib, re, sys
            config = pathlib.Path(sys.argv[1]).read_text()
            assert '_config_version: 33' in config
            assert 'provider: openai-codex' in config
            assert 'default: gpt-5.6-terra' in config
            assert 'provider: gemini' in config
            assert 'mcp_servers:' in config
            for name in ('context7', 'github', 'polylogue', 'lynchpin', 'sinex'):
                assert f'{name}:' in config, name
            assert 'external_dirs:' in config
            assert 'observability/nemo_relay' in config
            assert 'provider: local' in config
            assert 'silence_duration: 1.2' in config
            assert 'approvals:' in config
            assert re.search(r"mode: ['\"]off['\"]", config)
            for profile, required, forbidden in (
                ('research', ('web', 'browser', 'delegation'), ('terminal',)),
                ('orchestrate', ('skills', 'todo', 'memory', 'session_search', 'clarify'), ('terminal', 'file', 'code_execution', 'delegation', 'web', 'browser', 'tts')),
                ('mirror', ('memory', 'session_search', 'tts'), ('terminal', 'web', 'browser', 'delegation')),
            ):
                path = pathlib.Path.home() / '.hermes' / 'profiles' / profile / 'config.yaml'
                assert path.is_file(), path
                assert (path.parent / 'auth.json').is_symlink()
                assert (path.parent / '.env').is_symlink()
                assert (path.parent / 'SOUL.md').is_symlink()
                profile_config = path.read_text()
                for toolset in required:
                    assert f'- {toolset}' in profile_config, (profile, toolset)
                for toolset in forbidden:
                    assert f'- {toolset}' not in profile_config, (profile, toolset)
            research = (pathlib.Path.home() / '.hermes/profiles/research/config.yaml').read_text()
            assert 'reasoning_effort: high' in research
            assert 'max_concurrent_children: 6' in research
            assert 'max_iterations: 60' in research
            assert 'firecrawl:' in research
            orchestrate = (pathlib.Path.home() / '.hermes/profiles/orchestrate/config.yaml').read_text()
            assert 'agent-control:' in orchestrate
            PYCODE

            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/claude-lean" \
              "$HOME/.local/bin/claude-browser" \
              "$HOME/.local/bin/claude-deepseek" \
              "$HOME/.local/bin/claude-local" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/codex-lean" \
              "$HOME/.local/bin/codex-browser" \
              "$HOME/.local/bin/codex-deepseek" \
              "$HOME/.local/bin/codex-local" \
              "$HOME/.local/bin/gemini" \
              "$HOME/.local/bin/agy-sinnix" \
              "$HOME/.local/bin/hermes" \
              "$HOME/.local/bin/hermes-research" \
              "$HOME/.local/bin/hermes-orchestrate" \
              "$HOME/.local/bin/hermes-mirror" \
              "$HOME/.local/bin/codebase-memory-mcp" \
              "$HOME/.local/bin/serena" \
              "$HOME/.local/bin/serena-hooks" \
              "$HOME/.local/bin/bd-prime-if-present"; do
              test -x "$wrapper"
              bash -n "$wrapper"
            done

            grep -q 'HERMES_NEMO_RELAY_ATOF_ENABLED=1' "$HOME/.local/bin/hermes"
            grep -q 'HERMES_NEMO_RELAY_ATIF_ENABLED=1' "$HOME/.local/bin/hermes"
            grep -q 'HERMES_NEMO_RELAY_ATIF_SUBAGENT_EXPORT_MODE=all' "$HOME/.local/bin/hermes"
            for profile in research orchestrate mirror; do
              wrapper="$HOME/.local/bin/hermes-$profile"
              grep -Fq "export HERMES_HOME=\"\$HOME/.hermes/profiles/$profile\"" "$wrapper"
              grep -Fq 'export HERMES_INSTALL_DIR="$HOME/.hermes/hermes-agent"' "$wrapper"
            done

            jq -e '
              (has("mcpServers") | not) and
              .alwaysThinkingEnabled == true and
              .skipDangerousModePermissionPrompt == true and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks activate --client=claude-code"))) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("sessionstart-sinex-recall.sh"))) and
              ([.hooks.Stop[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks cleanup --client=claude-code")))
            ' ${inputs.self}/dots/claude/settings.json >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("agent-control")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.config/claude/mcp.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("polylogue")) and
              ($m | has("agent-control") | not) and
              ($m | has("lynchpin") | not) and
              ($m | has("serena") | not) and
              ($m | has("codebase-memory-mcp") | not) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "read"])
            ' "$HOME/.config/claude/mcp-lean.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("agent-control")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools")) and
              ($m | has("chrome-devtools-private")) and
              ($m | has("chrome-devtools-private-visible")) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.config/claude/mcp-browser.json" >/dev/null

            python3 - <<'PYCODE'
            import pathlib, tomllib

            def keys(path):
                return set(tomllib.loads(path.read_text()).get('mcp_servers', {}))

            def assert_has(name, actual, required, forbidden=()):
                missing = set(required) - actual
                unexpected = set(forbidden) & actual
                assert not missing, f"{name} missing {sorted(missing)}"
                assert not unexpected, f"{name} unexpectedly has {sorted(unexpected)}"

            config = tomllib.loads(pathlib.Path.home().joinpath('.codex/config.toml').read_text())
            assert config['approval_policy'] == 'never'
            assert config['sandbox_mode'] == 'danger-full-access'
            assert 'mcp_servers' not in config
            assert config['features']['hooks'] is True

            full = keys(pathlib.Path.home().joinpath('.codex/full.config.toml'))
            lean = keys(pathlib.Path.home().joinpath('.codex/lean.config.toml'))
            evidence = keys(pathlib.Path.home().joinpath('.codex/evidence.config.toml'))
            browser = keys(pathlib.Path.home().joinpath('.codex/browser.config.toml'))
            assert_has('full', full, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp', 'agent-control'}, {'chrome-devtools'})
            assert_has('lean', lean, {'github', 'context7', 'polylogue'}, {'agent-control', 'lynchpin', 'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('evidence', evidence, {'github', 'context7', 'polylogue', 'lynchpin'}, {'agent-control', 'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('browser', browser, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp', 'agent-control', 'chrome-devtools', 'chrome-devtools-private', 'chrome-devtools-private-visible'})

            # Alternate-backend profiles must layer a provider override while
            # retaining the full MCP surface; model names remain ordinary config.
            deepseek_path = pathlib.Path.home().joinpath('.codex/deepseek.config.toml')
            deepseek = tomllib.loads(deepseek_path.read_text())
            assert deepseek['model_provider'] == 'deepseek'
            assert deepseek['model_providers']['deepseek']['env_key']
            assert keys(deepseek_path) == full
            local_path = pathlib.Path.home().joinpath('.codex/local.config.toml')
            local = tomllib.loads(local_path.read_text())
            assert local['model_provider'] == 'local'
            assert local['model_providers']['local']['base_url'].startswith('http://127.0.0.1:')
            assert keys(local_path) == full
            for path_name, expected_role in [
                ('full.config.toml', 'write'),
                ('evidence.config.toml', 'write'),
                ('browser.config.toml', 'write'),
                ('lean.config.toml', 'read'),
            ]:
                data = tomllib.loads(pathlib.Path.home().joinpath('.codex', path_name).read_text())
                assert data['mcp_servers']['polylogue']['args'] == ['--role', expected_role]
            PYCODE

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("agent-control")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.gemini/settings.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("agent-control")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.gemini/config/mcp_config.json" >/dev/null

            jq -e '
              [.hooks.SessionStart[].hooks[].command]
              | any(contains("SINNIX_CODEX_PROFILE") and contains("serena-hooks activate --client=codex"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | index("bd-prime-if-present")
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | index("sessionstart-sinex-recall")
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              . as $root
              | all(["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"][]; . as $event | [$root.hooks[$event][]?.hooks[]?.command] | index("polylogue-hook \($event) --provider codex"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              . as $root
              | all(["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"][]; . as $event | [$root.hooks[$event][]?.hooks[]?.command] | index("polylogue-hook \($event) --provider claude-code"))
            ' '${../../dots/claude/settings.json}' >/dev/null

            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-full"
            grep -Fq 'export SINNIX_CLAUDE_PROFILE=lean' "$HOME/.local/bin/claude-lean"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp-lean.json"' "$HOME/.local/bin/claude-lean"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp-browser.json"' "$HOME/.local/bin/claude-browser"
            # DeepSeek/local variants use the full (default) MCP profile.
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-deepseek"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-local"
            grep -Fq 'https://api.deepseek.com/anthropic' "$HOME/.local/bin/claude-deepseek"
            grep -Fq 'ANTHROPIC_BASE_URL="http://127.0.0.1:4000"' "$HOME/.local/bin/claude-local"
            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/claude-lean" \
              "$HOME/.local/bin/claude-browser" \
              "$HOME/.local/bin/claude-deepseek" \
              "$HOME/.local/bin/claude-local"; do
              # Claude's supported task-capture override must default off the
              # bounded /tmp tmpfs while preserving an operator-supplied path.
              grep -Fq 'if [ -z "''${CLAUDE_CODE_TMPDIR:-}" ]; then' "$wrapper"
              grep -Fq 'export CLAUDE_CODE_TMPDIR=/realm/tmp/claude-code' "$wrapper"
              grep -Fq '/bin/install -d -m 0700 "$CLAUDE_CODE_TMPDIR"' "$wrapper"
            done
            grep -Fq 'codex_args=(--profile full)' "$HOME/.local/bin/codex"
            grep -Fq 'export SINNIX_CODEX_PROFILE=lean' "$HOME/.local/bin/codex-lean"
            grep -Fq 'codex_args=(--profile lean)' "$HOME/.local/bin/codex-lean"
            grep -Fq 'codex_args=(--profile full)' "$HOME/.local/bin/codex-full"
            grep -Fq 'codex_args=(--profile browser)' "$HOME/.local/bin/codex-browser"
            grep -Fq 'codex_args=(--profile deepseek)' "$HOME/.local/bin/codex-deepseek"
            grep -Fq 'codex_args=(--profile local)' "$HOME/.local/bin/codex-local"

            # All agent wrappers must bootstrap from npm packages without
            # launching through buildFHSEnv/bubblewrap.
            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/gemini"; do
              if grep -Fq 'agent-fhs' "$wrapper"; then
                echo "$wrapper still launches through agent-fhs" >&2
                exit 1
              fi
              grep -Fq 'launch.sh' "$wrapper"
              grep -Fq 'sinnix-agent-scope-exec "$STATE/launch.sh"' "$wrapper"
            done
            grep -Fq 'sinnix-agent-scope-exec "$HOME/.local/bin/agy"' "$HOME/.local/bin/agy-sinnix"
            if grep -R 'MemoryHigh\|MemoryMax\|MemorySwapMax' "$HOME/.local/bin/claude-full" "$HOME/.local/bin/codex" "$HOME/.local/bin/gemini"; then
              echo "agent wrappers must not hardcode resource limits; runtime inventory owns per-scope defaults" >&2
              exit 1
            fi
            for wrapper in "$HOME/.local/bin/claude-full" "$HOME/.local/bin/codex" "$HOME/.local/bin/gemini"; do
              grep -Fq 'sinnix-agent-npm-bootstrap' "$wrapper"
            done
            grep -Fq '@anthropic-ai/claude-code' "$HOME/.local/bin/claude-full"
            grep -Fq '@openai/codex' "$HOME/.local/bin/codex"
            grep -Fq '@google/gemini-cli' "$HOME/.local/bin/gemini"
            grep -Fq 'npm install -g "$npm_package"' '${../../scripts/sinnix-agent-npm-bootstrap}'
            grep -Fq 'export npm_config_prefix="$STATE/npm"' '${../../scripts/sinnix-agent-npm-bootstrap}'
            grep -Fq 'export NPM_CONFIG_PREFIX=' '${../../scripts/sinnix-agent-npm-bootstrap}'

            "$HOME/.local/bin/mcp-polylogue" --help | grep -q 'Start the Polylogue MCP stdio bridge'
            grep -Fq 'sinnix-mcp-sinex-script' "$(readlink -f "$HOME/.local/bin/mcp-sinex")"
            for helper in \
              "$HOME/.local/bin/sinnix-agent-status" \
              "$HOME/.local/bin/sinnix-chrome-control" \
              "$HOME/.local/bin/sinnix-hypr-control" \
              "$HOME/.local/bin/sinnix-keyboard-control" \
              "$HOME/.local/bin/sinnix-kitty-control" \
              "$HOME/.local/bin/sinnix-screenshot-control"; do
              test -x "$helper"
              bash -n "$helper"
            done
            grep -Fq 'private-sync-state' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'private-reseed-state --yes' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'preserved existing $TARGET Chrome profile' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'refusing destructive reseed without --yes' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'SINNIX_AGENT_CHROME_LIVE_PROFILE' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'cleanup_stale_private_locks' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'Deliberately do not sync Default/Local Extension Settings' "$HOME/.local/bin/sinnix-chrome-control"
            if grep -Fq 'sync_live_profile_path "Default/Local Extension Settings"' "$HOME/.local/bin/sinnix-chrome-control"; then
              echo "private profile sync must preserve extension recovery checkpoints" >&2
              exit 1
            fi

            agent_control_mcp=${inputs.self.packages.${system}.sinnix-agent-control-mcp}/bin/sinnix-agent-control-mcp
            test -x "$agent_control_mcp"
            mcp_fixture="$TMPDIR/agent-control-mcp"
            mkdir -p "$mcp_fixture/skill/scripts" "$mcp_fixture/state" "$mcp_fixture/repo"
            cat > "$mcp_fixture/skill/scripts/run_agent_prompt.sh" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail
            job_id=""
            state_dir=""
            log_file=""
            final_file=""
            workdir=""
            while [ "$#" -gt 0 ]; do
              case "$1" in
                --job-id) job_id="$2"; shift 2 ;;
                --job-state-dir) state_dir="$2"; shift 2 ;;
                --log-file) log_file="$2"; shift 2 ;;
                --last-file) final_file="$2"; shift 2 ;;
                --workdir) workdir="$2"; shift 2 ;;
                *) shift ;;
              esac
            done
            printf 'agent log for %s\n' "$job_id" > "$log_file"
            printf 'agent final for %s\n' "$job_id" > "$final_file"
            cat > "$state_dir/$job_id.json" <<JSON
            {"schema_version":1,"job_id":"$job_id","lifecycle":"completed","worktree":"$workdir","artifacts":{"log":"$log_file","final":"$final_file","json":""}}
            JSON
            EOF
            cat > "$mcp_fixture/skill/scripts/agent_job_control.sh" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail
            state_dir="$2"
            command="$3"
            case "$command" in
              list) printf '[%s]\n' "$(cat "$state_dir"/*.json)" ;;
              status) cat "$state_dir/$5.json" ;;
              interrupt) exit 0 ;;
              *) exit 64 ;;
            esac
            EOF
            chmod +x "$mcp_fixture/skill/scripts/run_agent_prompt.sh" "$mcp_fixture/skill/scripts/agent_job_control.sh"
            SINNIX_AGENT_ORCHESTRATION_SKILL_DIR="$mcp_fixture/skill" \
            SINNIX_AGENT_JOB_STATE_DIR="$mcp_fixture/state" \
            python3 - "$agent_control_mcp" "$mcp_fixture/repo" <<'PYCODE'
            import json, os, subprocess, sys

            server, repo = sys.argv[1:]
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "start_agent_job", "arguments": {"backend": "codex", "workdir": repo, "prompt": "implement the fixture"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_agent_jobs", "arguments": {}}},
            ]
            process = subprocess.Popen([server], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=os.environ.copy())
            assert process.stdin is not None and process.stdout is not None
            for request in requests:
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()
            responses = [json.loads(process.stdout.readline()) for _ in requests]
            assert responses[0]["result"]["serverInfo"]["name"] == "sinnix-agent-control"
            tools = {tool["name"] for tool in responses[1]["result"]["tools"]}
            assert tools == {"start_agent_job", "list_agent_jobs", "agent_job_status", "read_agent_job_output", "interrupt_agent_job"}
            job_id = responses[2]["result"]["structuredContent"]["job_id"]
            assert responses[3]["result"]["structuredContent"][0]["job_id"] == job_id
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "read_agent_job_output", "arguments": {"job_id": job_id, "artifact": "final"}}}) + "\n")
            process.stdin.flush()
            output = json.loads(process.stdout.readline())["result"]["structuredContent"]
            assert output["content"] == f"agent final for {job_id}\n"
            process.stdin.close()
            assert process.wait(timeout=5) == 0
            PYCODE
            grep -Fq 'sinnix-mcp-chrome-devtools-private' "$(readlink -f "$HOME/.local/bin/mcp-chrome-devtools-private")"
          '';
        }
      );
    in
    {
      checks = {
        agent-resource-policy = agentResourcePolicy;
        agent-npm-bootstrap-recovery = agentNpmBootstrapRecovery;
      };

      heavyChecks = {
        dev-agent-tools-runtime = devAgentToolsRuntime;
      };
    };
}
