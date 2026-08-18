# Agent CLI wrapper / MCP profile runtime checks (Claude, Codex, Gemini).
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
      mcpRegistry = import ../data/mcp-registry.nix { inherit lib; };
      launch = import ../launch.nix { inherit lib pkgs runtimeDefaults; };
      agentLanes = import ../data/agent-lanes.nix;
      # Derived from the lane registry rather than hand-listed: every declared
      # lane must produce an installed wrapper, and adding or retiring a lane
      # must not require editing this file in several places.
      laneWrapperFiles = map (binName: ".local/bin/${binName}") (
        (map (lane: lane.binName) (lib.attrValues agentLanes.claudeLanes))
        ++ (map (lane: lane.binName) (lib.attrValues agentLanes.codexLanes))
        ++ (map (name: "hermes-${name}") (lib.attrNames agentLanes.hermesProfiles))
      );
      # Each lane's wrapper must honour the registry entry it was rendered
      # from: the MCP config file its profile selects, the profile marker the
      # hooks branch on, and (for alternate backends) the endpoint the lane
      # declares. Derived here so a lane rename or a new backend needs no
      # edit in this file, and so a wrapper that stops following the registry
      # fails rather than a literal that only this test and the renderer know.
      claudeLaneWrapperChecks = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (
          _: lane:
          let
            wrapper = ''"$HOME/.local/bin/${lane.binName}"'';
            mcpFile = if lane.mcpProfile == "full" then "mcp" else "mcp-${lane.mcpProfile}";
          in
          ''
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/${mcpFile}.json"' ${wrapper}
            grep -Fq 'export SINNIX_CLAUDE_PROFILE=${lane.mcpProfile}' ${wrapper}
          ''
          + lib.optionalString (lane ? env) ''
            grep -Fq 'ANTHROPIC_BASE_URL="${lane.env.baseUrl}"' ${wrapper}
          ''
        ) agentLanes.claudeLanes
      );
      codexLaneWrapperChecks = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (
          _: lane:
          let
            wrapper = ''"$HOME/.local/bin/${lane.binName}"'';
          in
          ''
            grep -Fq 'codex_args=(--profile ${lane.mcpProfile})' ${wrapper}
            grep -Fq 'export SINNIX_CODEX_PROFILE=${lane.mcpProfile}' ${wrapper}
          ''
        ) agentLanes.codexLanes
      );
      expectedProfileServers =
        client: profiles:
        builtins.toJSON (
          lib.genAttrs profiles (
            profile: lib.attrNames (mcpRegistry.selectClientServersForProfile profile client)
          )
        );
      expectedClaudeProfileServersJson = expectedProfileServers "claude" [
        "full"
        "lean"
        "browser"
      ];
      expectedGeminiProfileServersJson = expectedProfileServers "gemini" [
        "full"
        "antigravity"
      ];
      expectedCodexProfileServersJson = expectedProfileServers "codex" [
        "full"
        "lean"
        "evidence"
        "browser"
      ];
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
              assertion = lib.hasInfix "${config.sinnix.paths.dotsRoot}/claude/settings-seed.json" activationText;
              message = "Claude settings.json must be seeded copy-if-absent from dots so the harness can persist UI state into a plain writable file.";
            }
            {
              assertion =
                (config.environment.etc."claude-code/managed-settings.json".source or null)
                == "${config.sinnix.paths.dotsRoot}/claude/managed-settings.json";
              message = "Claude managed settings must be deployed to /etc/claude-code as a symlink into the live dots checkout.";
            }
            {
              assertion = builtins.hasAttr ".config/claude/agents" hm.home.file;
              message = "Claude agent definitions must be linked as one directory from the shared dots tree.";
            }
            {
              assertion = builtins.hasAttr "sinnix-settings-env-lint" hm.systemd.user.services;
              message = "The settings environment audit service must be declared.";
            }
            {
              assertion = builtins.hasAttr "sinnix-settings-env-lint" hm.systemd.user.timers;
              message = "The settings environment audit timer must be declared.";
            }
            {
              assertion = builtins.hasAttr "sinnix-vacuity-judge" hm.systemd.user.services;
              message = "The bounded vacuity judge worker must be declared.";
            }
            {
              assertion = builtins.hasAttr "sinnix-vacuity-judge" hm.systemd.user.timers;
              message = "The bounded vacuity judge timer must be declared.";
            }
            {
              assertion = builtins.all (path: builtins.hasAttr path hm.home.file) [
                ".local/bin/sinnix-chrome-control"
                ".local/bin/sinnix-hypr-control"
                ".local/bin/sinnix-keyboard-control"
                ".local/bin/sinnix-kitty-control"
                ".local/bin/sinnix-screenshot-control"
              ];
              message = "Desktop control helpers must be installed through Home Manager.";
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
        homeFiles = laneWrapperFiles ++ [
          ".gemini/settings.json"
          ".gemini/config/mcp_config.json"
          ".gemini/config/skills"
          ".gemini/config/AGENTS.md"
          ".local/bin/gemini"
          ".local/bin/grok-sinnix"
          ".local/bin/agy-sinnix"
          ".local/bin/hermes"
          ".local/bin/serena"
          ".local/bin/serena-hooks"
          ".local/bin/bd-prime-if-present"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-chrome-devtools"
          ".local/bin/mcp-polylogue"
          ".local/bin/mcp-sinex"
          ".local/bin/sinnix-mcp-sweep"
          ".config/hermes/skills"
          ".config/claude/agents"
        ];
        fixtureAssets = [
          {
            target = ".local/bin/sinnix-chrome-control";
            source = ../../dots/_ai/skills/desktop-control-plane/scripts/chrome-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-hypr-control";
            source = ../../dots/_ai/skills/desktop-control-plane/scripts/hypr-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-keyboard-control";
            source = ../../dots/_ai/skills/desktop-control-plane/scripts/keyboard-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-kitty-control";
            source = ../../dots/_ai/skills/desktop-control-plane/scripts/kitty-remote-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-screenshot-control";
            source = ../../dots/_ai/skills/desktop-control-plane/scripts/screenshot-color-lab.sh;
            executable = true;
          }
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

      # Provably fails when: the wrapper renderer stops following the lane
      # registry (verified by hardcoding MCP_CONFIG to mcp.json in
      # backends.nix, which breaks every non-full lane), a rendered MCP
      # profile's server set diverges from the registry's own selection, a
      # Hermes profile gains a toolset its capability boundary forbids, or a
      # wrapper stops launching through sinnix-agent-scope-exec.
      #
      # Note: changing flake/data/agent-lanes.nix alone does NOT fail this
      # check, and should not -- both the renderer and these expectations
      # derive from that registry, which is the point.
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
            test "$(readlink -f "$HOME/.gemini/config/mcp_config.json")" = ${agentToolsAntigravityMcpConfigSource}
            mkdir -p "$HOME/.hermes"
            cp ${agentToolsHermesConfigSource} "$HOME/.hermes/config.yaml"
            chmod 600 "$HOME/.hermes/config.yaml"
            ${lib.concatStringsSep "\n" (
              lib.mapAttrsToList (name: source: ''
                mkdir -p "$HOME/.hermes/profiles/${name}"
                ln -s ../../auth.json "$HOME/.hermes/profiles/${name}/auth.json"
                ln -s ../../.env "$HOME/.hermes/profiles/${name}/.env"
                ln -s ../../SOUL.md "$HOME/.hermes/profiles/${name}/SOUL.md"
                cp ${source} "$HOME/.hermes/profiles/${name}/config.yaml"
                chmod 600 "$HOME/.hermes/profiles/${name}/config.yaml"
              '') agentToolsHermesProfileConfigSources
            )}
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
            assert 'provider: openai-codex' in config
            assert 'provider: gemini' in config
            assert 'mcp_servers:' in config
            for name in ('context7', 'github', 'polylogue', 'lynchpin', 'sinex'):
                assert f'{name}:' in config, name
            assert 'external_dirs:' in config
            assert 'observability/nemo_relay' in config
            assert 'approvals:' in config
            assert re.search(r"mode: ['\"]off['\"]", config)
            local_profile = (pathlib.Path.home() / '.hermes/profiles/local/config.yaml').read_text()
            assert 'provider: custom' in local_profile
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
            assert 'firecrawl:' in research
            orchestrate = (pathlib.Path.home() / '.hermes/profiles/orchestrate/config.yaml').read_text()
            assert 'agent-control:' in orchestrate
            PYCODE

            for wrapper in \
              ${lib.concatMapStringsSep " \\\n              " (f: ''"$HOME/${f}"'') laneWrapperFiles} \
              "$HOME/.local/bin/gemini" \
              "$HOME/.local/bin/grok-sinnix" \
              "$HOME/.local/bin/agy-sinnix" \
              "$HOME/.local/bin/hermes" \
              "$HOME/.local/bin/serena" \
              "$HOME/.local/bin/serena-hooks" \
              "$HOME/.local/bin/bd-prime-if-present"; do
              test -x "$wrapper"
              bash -n "$wrapper"
            done

            jq -e '
              (has("mcpServers") | not) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks activate --client=claude-code"))) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("sessionstart-sinex-recall.sh"))) and
              ([.hooks.Stop[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks cleanup --client=claude-code")))
            ' ${inputs.self}/dots/claude/managed-settings.json >/dev/null

            # Rendered profile configs must match the registry's own computed
            # selection -- membership is derived from mcp-registry.nix at eval
            # time, never frozen as literals.
            for pair in \
              "mcp.json full" "mcp-lean.json lean" "mcp-browser.json browser"; do
              file="''${pair%% *}"; profile="''${pair##* }"
              rendered="$(jq -r '.mcpServers | keys | sort | join(",")' "$HOME/.config/claude/$file")"
              expected="$(jq -r --arg p "$profile" '.[$p] | sort | join(",")' <<'EOF_EXPECTED'
            ${expectedClaudeProfileServersJson}
            EOF_EXPECTED
            )"
              if [ "$rendered" != "$expected" ]; then
                echo "claude $file servers ($rendered) != registry selection ($expected)" >&2
                exit 1
              fi
            done

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
            assert 'mcp_servers' not in config
            assert config['features']['hooks'] is True

            full = keys(pathlib.Path.home().joinpath('.codex/full.config.toml'))
            lean = keys(pathlib.Path.home().joinpath('.codex/lean.config.toml'))
            evidence = keys(pathlib.Path.home().joinpath('.codex/evidence.config.toml'))
            browser = keys(pathlib.Path.home().joinpath('.codex/browser.config.toml'))
            import json
            expected = json.loads('${expectedCodexProfileServersJson}')
            for profile_name, actual in (('full', full), ('lean', lean), ('evidence', evidence), ('browser', browser)):
                assert actual == set(expected[profile_name]), (
                    f"codex {profile_name} servers {sorted(actual)} != registry selection {sorted(expected[profile_name])}"
                )

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

            # Same registry-derived contract as the claude configs above:
            # rendered gemini server sets must equal the registry selection.
            for pair in \
              ".gemini/settings.json full" ".gemini/config/mcp_config.json antigravity"; do
              file="''${pair%% *}"; profile="''${pair##* }"
              rendered="$(jq -r '.mcpServers | keys | sort | join(",")' "$HOME/$file")"
              expected="$(jq -r --arg p "$profile" '.[$p] | sort | join(",")' <<'EOF_EXPECTED_GEMINI'
            ${expectedGeminiProfileServersJson}
            EOF_EXPECTED_GEMINI
            )"
              if [ "$rendered" != "$expected" ]; then
                echo "gemini $file servers ($rendered) != registry selection ($expected)" >&2
                exit 1
              fi
            done

            jq -e '
              [.hooks.SessionStart[].hooks[].command]
              | any(contains("SINNIX_CODEX_PROFILE") and contains("serena-hooks activate --client=codex"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | index("bd-prime-if-present")
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | any(contains("sessionstart-sinex-recall.sh"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            ${claudeLaneWrapperChecks}
            ${codexLaneWrapperChecks}

            # Every agent wrapper launches its npm-bootstrapped entry point
            # through the scope wrapper, so the process lands in the agent
            # slice rather than in the caller's cgroup.
            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/gemini"; do
              grep -Fq 'launch.sh' "$wrapper"
              grep -Fq 'sinnix-agent-scope-exec "$STATE/launch.sh"' "$wrapper"
            done
            grep -Fq 'sinnix-agent-scope-exec "$HOME/.local/bin/agy"' "$HOME/.local/bin/agy-sinnix"
            grep -Fq 'sinnix-agent-scope-exec "$HOME/.grok/bin/grok"' "$HOME/.local/bin/grok-sinnix"
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
              "$HOME/.local/bin/sinnix-chrome-control" \
              "$HOME/.local/bin/sinnix-hypr-control" \
              "$HOME/.local/bin/sinnix-keyboard-control" \
              "$HOME/.local/bin/sinnix-kitty-control" \
              "$HOME/.local/bin/sinnix-screenshot-control"; do
              if ! test -x "$helper"; then
                echo "expected executable helper is missing: $helper" >&2
                exit 1
              fi
              bash -n "$helper"
            done
            agent_control_mcp=${
              inputs.self.packages.${system}.sinnix-agent-control-mcp
            }/bin/sinnix-agent-control-mcp
            test -x "$agent_control_mcp"
          '';
        }
      );
      scopeWrapperFixture =
        pkgs.runCommand "scope-wrapper-fixture"
          {
            # No jq: the wrapper resolves a command's class from the case body
            # rendered into the rc below, not from the serialized inventory.
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${../../flake/tests/scope-wrapper.sh} ${pkgs.writeText "sinnix-direnvrc-rendered" (runtimeDefaults.renderDirenvrc (builtins.readFile ../../scripts/sinnix-direnvrc))}
            touch "$out"
          '';
      agentJobHandleFixture =
        pkgs.runCommand "agent-job-handle-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.git
              pkgs.gawk
              pkgs.gnugrep
              pkgs.gnused
              pkgs.jq
              pkgs.util-linux
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME"
            export PATH=${
              lib.makeBinPath [
                pkgs.bash
                pkgs.coreutils
                pkgs.findutils
                pkgs.git
                pkgs.gawk
                pkgs.gnugrep
                pkgs.gnused
                pkgs.jq
                pkgs.util-linux
              ]
            }
            fixture_source="$TMPDIR/source"
            fixture_skill="$fixture_source/dots/_ai/skills/agent-orchestration"
            mkdir -p "$fixture_skill/scripts" "$fixture_source/scripts"
            cp ${../../dots/_ai/skills/agent-orchestration/scripts/run_agent_prompt.sh} "$fixture_skill/scripts/run_agent_prompt.sh"
            cp ${../../dots/_ai/skills/agent-orchestration/scripts/agent_job_control.sh} "$fixture_skill/scripts/agent_job_control.sh"
            cp ${../../scripts/sinnix-agent-scope-exec} "$fixture_source/scripts/sinnix-agent-scope-exec"
            chmod +x "$fixture_skill/scripts/"* "$fixture_source/scripts/"*
            patchShebangs "$fixture_skill/scripts" "$fixture_source/scripts"
            export SINNIX_AGENT_TEST_REPO_ROOT="$fixture_source"
            export SINNIX_AGENT_TEST_SKILL_DIR="$fixture_skill"
            # The launcher is generated (flake/launch.nix), so there is no
            # scripts/sinnix-scope to copy. Point the test at the harness
            # rather than the wrapped package: the wrapper prepends systemd to
            # PATH, and this test's whole technique is shadowing systemd-run
            # with a recorder. Same rendered text either way.
            export SINNIX_AGENT_TEST_SCOPE_BIN=${launch.dispatcher.passthru.harness}
            ${pkgs.bash}/bin/bash ${../../dots/_ai/skills/agent-orchestration/tests/test_agent_job_handles.sh}
            touch "$out"
          '';
      mcpSweepFixture =
        pkgs.runCommand "mcp-sweep-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.gawk
              pkgs.jq
              pkgs.procps
            ];
          }
          ''
            sweep="$TMPDIR/sinnix-mcp-sweep"
            cp ${../../scripts/sinnix-mcp-sweep} "$sweep"
            chmod +x "$sweep"
            patchShebangs "$sweep"
            ${pkgs.bash}/bin/bash ${../../flake/tests/mcp-sweep.sh} "$sweep"
            touch "$out"
          '';
      preflightFixture =
        pkgs.runCommand "preflight-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.gawk
              pkgs.gnugrep
              pkgs.jq
              pkgs.procps
              pkgs.systemd
              pkgs.util-linux
            ];
          }
          ''
            preflight="$TMPDIR/sinnix-preflight"
            cp ${../../scripts/sinnix-preflight} "$preflight"
            chmod +x "$preflight"
            sed -i '1c#!${pkgs.bashInteractive}/bin/bash' "$preflight"
            ${pkgs.bash}/bin/bash ${../../flake/tests/preflight.sh} "$preflight"
            touch "$out"
          '';
      kittyAgentHereFixture =
        pkgs.runCommand "kitty-agent-here-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
              pkgs.gnugrep
              pkgs.gnused
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            helper="$TMPDIR/kitty-remote-control.sh"
            cp ${../../dots/_ai/skills/desktop-control-plane/scripts/kitty-remote-control.sh} "$helper"
            chmod +x "$helper"
            patchShebangs "$helper"
            ${pkgs.bash}/bin/bash ${../../flake/tests/kitty-agent-here.sh} "$helper"
            touch "$out"
          '';
      bdSafetyHookFixture =
        pkgs.runCommand "bd-safety-hook-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            hook="$TMPDIR/pretooluse-bash.sh"
            cp ${../../dots/claude/hooks/pretooluse-bash.sh} "$hook"
            chmod +x "$hook"
            patchShebangs "$hook"
            ${pkgs.bash}/bin/bash ${../../flake/tests/bd-safety.sh} "$hook"
            touch "$out"
          '';
      egressGuardFixture =
        pkgs.runCommand "egress-guard-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            scanner="$TMPDIR/sinnix-egress-scan"
            cp ${../../scripts/sinnix-egress-scan} "$scanner"
            chmod +x "$scanner"
            patchShebangs "$scanner"
            ${pkgs.bash}/bin/bash ${../../flake/tests/egress-guard.sh} "$scanner" "$TMPDIR/egress"
            touch "$out"
          '';
      contextHandoffFixture =
        pkgs.runCommand "context-handoff-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.gnugrep
              pkgs.jq
              pkgs.ripgrep
            ];
          }
          ''
            writer="$TMPDIR/sinnix-context-handoff"
            cp ${../../scripts/sinnix-context-handoff} "$writer"
            chmod +x "$writer"
            patchShebangs "$writer"
            ${pkgs.bash}/bin/bash ${../../flake/tests/context-handoff.sh} "$writer"
            touch "$out"
          '';
      skillAuthoringFixture =
        pkgs.runCommand "skill-authoring-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            validator="$TMPDIR/validate_skill.py"
            cp ${../../dots/_ai/skills/skill-authoring/scripts/validate_skill.py} "$validator"
            chmod +x "$validator"
            patchShebangs "$validator"
            ${pkgs.bash}/bin/bash ${../../flake/tests/skill-authoring.sh} "$validator"
            touch "$out"
          '';
      desktopCaptureFixture =
        pkgs.runCommand "desktop-capture-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
            ];
          }
          ''
            ocr="$TMPDIR/hyprland-ocr"
            dismiss="$TMPDIR/dismiss-scratchpads"
            cp ${../../scripts/hyprland-ocr} "$ocr"
            cp ${../../scripts/dismiss-scratchpads} "$dismiss"
            chmod +x "$ocr" "$dismiss"
            patchShebangs "$ocr" "$dismiss"
            ${pkgs.bash}/bin/bash ${../../flake/tests/desktop-capture.sh} "$ocr" "$dismiss"
            touch "$out"
          '';
      claudeJudgeFixture =
        pkgs.runCommand "claude-judge-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            judge="$TMPDIR/sinnix-claude-judge"
            review="$TMPDIR/run-review.sh"
            cp ${../../scripts/sinnix-claude-judge} "$judge"
            cp ${../../dots/_ai/skills/adversarial-loop/scripts/run-review.sh} "$review"
            chmod +x "$judge" "$review"
            patchShebangs "$judge" "$review"
            ${pkgs.bash}/bin/bash ${../../flake/tests/claude-judge.sh} "$judge" "$review"
            touch "$out"
          '';
      vacuitySamplerFixture =
        pkgs.runCommand "vacuity-sampler-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            sampler="$TMPDIR/sinnix-vacuity-sampler"
            cp ${../../scripts/sinnix-vacuity-sampler} "$sampler"
            chmod +x "$sampler"
            patchShebangs "$sampler"
            ${pkgs.bash}/bin/bash ${../../flake/tests/vacuity-sampler.sh} "$sampler"
            touch "$out"
          '';
      recoverySkillsFixture =
        pkgs.runCommand "recovery-skills-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.jq
            ];
          }
          ''
            freeze="$TMPDIR/freeze.sh"
            recover="$TMPDIR/recover-probe.sh"
            cp ${../../dots/_ai/skills/incident-evidence-freeze/scripts/freeze.sh} "$freeze"
            cp ${../../dots/_ai/skills/recovery-decision-tree/scripts/recover-probe.sh} "$recover"
            chmod +x "$freeze" "$recover"
            patchShebangs "$freeze" "$recover"
            ${pkgs.bash}/bin/bash ${../../flake/tests/recovery-skills.sh} "$freeze" "$recover"
            touch "$out"
          '';
      hooksHarnessFixture =
        pkgs.runCommand "hooks-harness-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnused
              pkgs.jq
              pkgs.python3
              pkgs.shellcheck
            ];
          }
          ''
            hooks="$TMPDIR/hooks"
            settings="$TMPDIR/settings.json"
            sampler="$TMPDIR/sinnix-vacuity-sampler"
            mkdir -p "$hooks"
            cp ${../../dots/claude/hooks}/*.sh "$hooks/"
            cp ${../../dots/claude/managed-settings.json} "$settings"
            cp ${../../scripts/sinnix-vacuity-sampler} "$sampler"
            chmod +x "$hooks"/*.sh
            chmod +x "$sampler"
            patchShebangs "$hooks"
            patchShebangs "$sampler"
            ${pkgs.bash}/bin/bash ${../../flake/tests/hooks-harness.sh} "$hooks" "$settings" "$sampler"
            touch "$out"
          '';
      agentDefinitionsFixture =
        pkgs.runCommand "agent-definitions-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
              pkgs.gnugrep
              pkgs.git
              pkgs.jq
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${../../flake/tests/agent-definitions.sh} ${../../dots/claude/agents}
            touch "$out"
          '';
      settingsEnvLintFixture =
        pkgs.runCommand "settings-env-lint-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            scanner="$TMPDIR/sinnix-settings-env-lint"
            cp ${../../scripts/sinnix-settings-env-lint} "$scanner"
            chmod +x "$scanner"
            patchShebangs "$scanner"
            ${pkgs.bash}/bin/bash ${../../flake/tests/settings-env-lint.sh} "$scanner"
            touch "$out"
          '';
      agentProfileBenchmarkFixture =
        pkgs.runCommand "agent-profile-benchmark-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            benchmark="$TMPDIR/sinnix-agent-profile-benchmark"
            cp ${../../scripts/sinnix-agent-profile-benchmark} "$benchmark"
            chmod +x "$benchmark"
            patchShebangs "$benchmark"
            ${pkgs.bash}/bin/bash ${../../flake/tests/agent-profile-benchmark.sh} "$benchmark"
            touch "$out"
          '';
    in
    {
      checks = {
        agent-resource-policy = agentResourcePolicy;
        agent-npm-bootstrap-recovery = agentNpmBootstrapRecovery;
        scope-wrapper = scopeWrapperFixture;
        agent-job-handles = agentJobHandleFixture;
        mcp-sweep = mcpSweepFixture;
        preflight = preflightFixture;
        kitty-agent-here = kittyAgentHereFixture;
        bd-safety-hook = bdSafetyHookFixture;
        egress-guard = egressGuardFixture;
        context-handoff = contextHandoffFixture;
        skill-authoring = skillAuthoringFixture;
        desktop-capture = desktopCaptureFixture;
        claude-judge = claudeJudgeFixture;
        vacuity-sampler = vacuitySamplerFixture;
        recovery-skills = recoverySkillsFixture;
        hooks-harness = hooksHarnessFixture;
        agent-definitions = agentDefinitionsFixture;
        settings-env-lint = settingsEnvLintFixture;
        agent-profile-benchmark = agentProfileBenchmarkFixture;
      };

      checks = {
        dev-agent-tools-runtime = devAgentToolsRuntime;
      };
    };
}
