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
            test -L "$HOME/.config/claude/mcp.json"

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
              "$HOME/.local/bin/codebase-memory-mcp" \
              "$HOME/.local/bin/serena" \
              "$HOME/.local/bin/serena-hooks" \
              "$HOME/.local/bin/bd-prime-if-present"; do
              test -x "$wrapper"
              bash -n "$wrapper"
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
              ($m | has("github") and has("context7")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.config/claude/mcp.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("polylogue")) and
              ($m | has("lynchpin") | not) and
              ($m | has("serena") | not) and
              ($m | has("codebase-memory-mcp") | not) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "read"])
            ' "$HOME/.config/claude/mcp-lean.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7")) and
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
            assert_has('full', full, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp'}, {'chrome-devtools'})
            assert_has('lean', lean, {'github', 'context7', 'polylogue'}, {'lynchpin', 'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('evidence', evidence, {'github', 'context7', 'polylogue', 'lynchpin'}, {'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('browser', browser, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp', 'chrome-devtools', 'chrome-devtools-private', 'chrome-devtools-private-visible'})

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
              ($m | has("github") and has("context7")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.gemini/settings.json" >/dev/null

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
              grep -Fq 'run_agent_scoped "$STATE/launch.sh"' "$wrapper"
            done
            if grep -R 'MemoryHigh\|MemoryMax\|MemorySwapMax' "$HOME/.local/bin/claude-full" "$HOME/.local/bin/codex" "$HOME/.local/bin/gemini"; then
              echo "interactive agent wrappers must not impose shared memory caps" >&2
              exit 1
            fi
            grep -Fq 'npm install -g @anthropic-ai/claude-code' "$HOME/.local/bin/claude-full"
            grep -Fq 'npm install -g @openai/codex' "$HOME/.local/bin/codex"
            grep -Fq 'npm install -g @google/gemini-cli' "$HOME/.local/bin/gemini"
            grep -Fq 'export npm_config_prefix="$HOME/.local/state/$state_dir_name/npm"' '${../../scripts/sinnix-agent-npm-bootstrap}'
            grep -Fq 'export NPM_CONFIG_PREFIX="$HOME/.local/state/$state_dir_name/npm"' '${../../scripts/sinnix-agent-npm-bootstrap}'

            "$HOME/.local/bin/mcp-polylogue" --help | grep -q 'Start the Polylogue MCP stdio bridge'
            grep -Fq 'sinex-mcp-server' "$HOME/.local/bin/mcp-sinex"
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
            grep -Fq 'SINNIX_AGENT_CHROME_LIVE_PROFILE' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'private-sync-state' "$HOME/.local/bin/mcp-chrome-devtools-private"
          '';
        }
      );
    in
    {
      heavyChecks = {
        dev-agent-tools-runtime = devAgentToolsRuntime;
      };
    };
}
