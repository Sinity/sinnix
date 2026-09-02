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
      polylogueSentinelDataDir = "/tmp/sinnix-polylogue-agent-tools-sentinel";
      # The packaged binary, not a copy of the source with a hand-patched
      # shebang: the wrapper and the withPackages interpreter that discovery
      # builds are part of what these fixtures are testing, and a fixture that
      # rebuilds them itself passes while the real command is broken.
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
      runtimeDefaults = import ../data/runtime-defaults.nix { inherit lib; };
      mcpRegistry = import ../data/mcp-registry.nix { inherit lib; };
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
            sinnix.services.clodex.enable = true;
            sinnix.services.polylogue.dataDir = polylogueSentinelDataDir;
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
              assertion = builtins.hasAttr "sinnix-clodex" hm.systemd.user.services;
              message = "Clodex must run as an advertised local user service for Claude Code child-process routing.";
            }
            {
              assertion = lib.hasInfix "models --json" (toString hm.systemd.user.services.sinnix-clodex.Service.ExecStartPre);
              message = "Clodex startup must inspect aliases through its structured JSON interface.";
            }
            {
              assertion = lib.hasInfix "patch is stale" (toString hm.systemd.user.services.sinnix-clodex.Service.ExecStartPre);
              message = "Clodex startup must fail readiness with an actionable stale-patch status.";
            }
            {
              assertion =
                let
                  preStart = toString hm.systemd.user.services.sinnix-clodex.Service.ExecStartPre;
                in
                lib.hasInfix "models --unalias" preStart
                && lib.hasInfix "luna=clodex:openai-oauth:gpt-5.6-luna" preStart
                && lib.hasInfix "sol=clodex:openai-oauth:gpt-5.6-sol" preStart
                && lib.hasInfix "terra=clodex:openai-oauth:gpt-5.6-terra" preStart;
              message = "Clodex startup must converge the complete declared alias set.";
            }
            {
              assertion =
                let
                  preStart = toString hm.systemd.user.services.sinnix-clodex.Service.ExecStartPre;
                in
                lib.hasInfix ".claudeVersion" preStart
                && lib.hasInfix ".patchedSize" preStart
                && lib.hasInfix "run clodex patch" preStart;
              message = "Clodex startup must validate the structured patch manifest without rewriting the CLI.";
            }
            {
              assertion = lib.any (
                entry: (if builtins.isAttrs entry then entry.directory else entry) == ".clodex"
              ) config.sinnix.persistence.home.directories;
              message = "Clodex's non-secret OAuth recovery state must survive impermanence.";
            }
            # These two jobs render through mkScheduledJob at the NixOS level
            # (/etc/systemd/user), not through home-manager — the two
            # namespaces never merge, so asserting the right carrier is the
            # test's whole value.
            {
              assertion = builtins.hasAttr "sinnix-settings-env-lint" config.systemd.user.services;
              message = "The settings environment audit service must be declared.";
            }
            {
              assertion = builtins.hasAttr "sinnix-settings-env-lint" config.systemd.user.timers;
              message = "The settings environment audit timer must be declared.";
            }
            {
              assertion = builtins.all (path: builtins.hasAttr path hm.home.file) [
                ".local/bin/sinnix-chrome-control"
                ".local/bin/sinnix-hypr-control"
                ".local/bin/sinnix-keyboard-control"
                ".local/bin/sinnix-kitty-control"
                ".local/bin/sinnix-screenshot-control"
                ".local/bin/lane"
              ];
              message = "Agent control helpers must be installed through Home Manager.";
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
          ".local/bin/claude-clodex"
          ".local/bin/clodex"
          ".local/bin/clodex-claude"
          ".local/bin/sinnix-clodex-server"
          ".gemini/settings.json"
          ".gemini/config/mcp_config.json"
          ".gemini/config/skills"
          ".gemini/config/AGENTS.md"
          ".local/bin/gemini"
          ".local/bin/grok-sinnix"
          ".local/bin/agy-sinnix"
          ".local/bin/hermes"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-chrome-devtools"
          ".local/bin/mcp-polylogue"
          ".local/bin/mcp-sinex"
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
          {
            target = ".local/bin/lane";
            source = ../../dots/_ai/skills/agent-runtime/scripts/lane;
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

      # Provably fails when: a generic runtime, browser, shell or agent binary
      # is added to the earlyoom emergency avoid list (verified by adding
      # "node"), which would make the last-resort OOM killer skip exactly the
      # processes that cause the pressure.
      #
      # Note: this is an eval-time assert, so it takes down the whole checks
      # attribute rather than one derivation.
      agentResourcePolicy =
        let
          avoidPattern = runtimeDefaults.earlyoomEmergencyAvoidPattern;
          userSlices = runtimeDefaults.slices.user;
          managedWork = userSlices.sinnixd;
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
        assert lib.assertMsg (
          managedWork.CPUWeight < userSlices.app.CPUWeight
          && managedWork.IOWeight < userSlices.app.IOWeight
          && managedWork.MemoryHigh == "20G"
          && !(managedWork ? MemoryMax)
          && managedWork.ManagedOOMSwap == "kill"
          && managedWork.ManagedOOMMemoryPressure == "kill"
          && managedWork.ManagedOOMMemoryPressureLimit == "50%"
          && managedWork.ManagedOOMMemoryPressureDurationSec == "30s"
          && userSlices.app.MemoryLow == "6G"
          && userSlices.session.MemoryLow == "6G"
        ) "sinnixd work must yield to protected interactive slices without a hard CPU or memory cap";
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
      # Hermes profile gains a toolset its capability boundary forbids.
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
            test -x "$HOME/.local/bin/lane"
            bash -n "$HOME/.local/bin/lane"
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

            bash -n "$HOME/.local/bin/claude-clodex"
            bash -n "$HOME/.local/bin/clodex"
            bash -n "$HOME/.local/bin/clodex-claude"
            bash -n "$HOME/.local/bin/sinnix-clodex-server"
            for wrapper in \
              ${lib.concatMapStringsSep " \\\n              " (f: ''"$HOME/${f}"'') laneWrapperFiles} \
              "$HOME/.local/bin/gemini" \
              "$HOME/.local/bin/grok-sinnix" \
              "$HOME/.local/bin/agy-sinnix" \
              "$HOME/.local/bin/hermes"; do
              test -x "$wrapper"
              bash -n "$wrapper"
            done

            jq -e '
              (has("mcpServers") | not) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("sessionstart-sinex-recall.sh"))) and
              ([.hooks.Stop[].hooks[].command]
                | any(. == "polylogue-hook Stop --provider claude-code"))
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
              [.hooks.Stop[].hooks[].command]
              | any(. == "polylogue-hook Stop --provider codex")
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | any(contains("sessionstart-sinex-recall.sh"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            ${claudeLaneWrapperChecks}
            ${codexLaneWrapperChecks}
            grep -Fq '@bman654/clodex' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'CLODEX_REQUIRE_SERVER=1' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'CLODEX_CREDENTIAL_HELPER=' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'claude-wrapper.js' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'claude-code/bin/claude.exe' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-clodex"
            grep -Fq 'export SINNIX_CLAUDE_PROFILE=full' "$HOME/.local/bin/claude-clodex"
            grep -Fq '@bman654/clodex' "$HOME/.local/bin/clodex"
            grep -Fq 'CLODEX_CLAUDE_PATH="$claude_binary"' "$HOME/.local/bin/clodex"
            grep -Fq 'TWEAKCC_CC_INSTALLATION_PATH="$claude_binary"' "$HOME/.local/bin/clodex"
            grep -Fq 'claude-code/bin/claude.exe' "$HOME/.local/bin/clodex"
            grep -Fq 'claude-wrapper.js' "$HOME/.local/bin/clodex-claude"
            grep -Fq 'CLODEX_CREDENTIAL_HELPER=' "$HOME/.local/bin/clodex-claude"
            grep -Fq 'server --proxy' "$HOME/.local/bin/sinnix-clodex-server"
            grep -Fq 'CLODEX_CREDENTIAL_HELPER=' "$HOME/.local/bin/sinnix-clodex-server"
            jq -e '.env.CLAUDE_CODE_PROCESS_WRAPPER == "/home/sinity/.local/bin/clodex-claude"' ${inputs.self}/dots/claude/managed-settings.json >/dev/null

            # Every outer agent wrapper must enter agent.slice before its
            # bootstrap runs. A missing scope launch leaves npm/bootstrap work
            # in the terminal session and makes the cgroup regression invisible
            # to admission.
            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/gemini"; do
              grep -Fq 'launch.sh' "$wrapper"
              grep -Fq '/proc/self/cgroup' "$wrapper"
              grep -Fq -- '--slice=agent.slice' "$wrapper"
            done
            if grep -R 'MemoryHigh\|MemoryMax\|MemorySwapMax' "$HOME/.local/bin/claude-full" "$HOME/.local/bin/codex" "$HOME/.local/bin/gemini"; then
              echo "agent wrappers must not hardcode resource limits" >&2
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
            grep -Fq '/etc/sinnix/agent-gateway.json' "$agent_control_mcp"
          '';
        }
      );
      direnvDirectCommandsFixture =
        pkgs.runCommand "direnv-direct-commands-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.git
            ];
          }
          ''
            fixture_bin="$TMPDIR/bin"
            mkdir -p "$fixture_bin"
            printf '#!${pkgs.bash}/bin/bash\nprintf "%s\\n" direct\n' direct > "$fixture_bin/direct-command"
            chmod +x "$fixture_bin/direct-command"
            export PATH="$fixture_bin:$PATH"
            before_path="$PATH"
            use_flake() { return 0; }
            source ${../../scripts/sinnix-direnvrc}
            use_flake
            test "$PATH" = "$before_path"
            test "$(command -v direct-command)" = "$fixture_bin/direct-command"
            test "$(direct-command)" = direct
            touch "$out"
          '';
      agentctlOperationFixture =
        pkgs.runCommand "agentctl-operation-contract-fixture"
          {
            nativeBuildInputs = [ pkgs.python3 ];
          }
          ''
            ${pkgs.python3}/bin/python - <<'PY'
            import tomllib
            from pathlib import Path

            descriptor = Path("${inputs.self}/.agentctl/project.toml")
            operation = tomllib.loads(descriptor.read_text())["operations"]["sinex_cache_prebuild"]
            assert operation["exec"] == [
                "sinnix-sinex-cache-prebuild",
                "--flake-dir",
                "/realm/project/sinnix",
                "--system",
                "x86_64-linux",
            ]
            assert operation["pool"] == "bulk"
            assert operation["result"] == "exit"
            assert operation["exclusive_keys"] == ["sinnix:nix-store-pressure", "sinex:cache-prebuild"]
            assert operation["estimate_memory_bytes"] == 12 * 1024 * 1024 * 1024
            assert operation["scratch"] == "nvme"
            assert operation["timeout_seconds"] == 7200
            PY
            touch "$out"
          '';
      agentctlOperationLaunchFixture =
        pkgs.runCommand "agentctl-operation-launch-fixture"
          {
            nativeBuildInputs = [ pkgs.python3 ];
          }
          ''
            export PYTHONPATH="${
              lib.concatStringsSep ":" (
                map (package: "${package}/${pkgs.python3.sitePackages}") [
                  scriptRegistry.packageSet.sinnixd
                  scriptRegistry.packageSet.sinnix-mcp
                  scriptRegistry.packageSet.sinnix-lib
                ]
              )
            }"
            ${pkgs.python3}/bin/python - <<'PY'
            import os
            from pathlib import Path
            from tempfile import TemporaryDirectory

            from sinnixd.jobs import GenericJobStore, GenericJobs
            from sinnixd.projects import ProjectCatalog


            class FakeSystemd:
                def __init__(self):
                    self.started = []

                def start(self, **kwargs):
                    self.started.append(kwargs)

                def show(self, _unit, *, timeout_seconds=0.25):
                    return {
                        "LoadState": "loaded",
                        "ActiveState": "active",
                        "SubState": "running",
                        "MainPID": "42",
                        "Result": "success",
                    }

                def stop(self, _unit):
                    pass


            root = Path("${inputs.self}")
            project = ProjectCatalog([root]).get("sinnix")
            operation = project.operation("sinex_cache_prebuild")
            assert operation.timeout_seconds == 7200
            assert operation.command == (
                "sinnix-sinex-cache-prebuild",
                "--flake-dir",
                "/realm/project/sinnix",
                "--system",
                "x86_64-linux",
            )
            with TemporaryDirectory() as state:
                os.environ["SINNIXD_NVME_SCRATCH_ROOT"] = str(Path(state) / "nvme-scratch")
                systemd = FakeSystemd()
                jobs = GenericJobs(
                    systemd,
                    GenericJobStore(Path(state)),
                    pressure_probe=lambda: {"memory_full_avg10": 0.0},
                )
                started = jobs.start_declared(
                    project=project,
                    operation=operation,
                    correlation_id="fixture",
                    parameters={},
                )
                record = jobs.store.load(started["job_id"])
                expected = project.environment.command_for(
                    operation.command,
                    overrides={"TMPDIR": str(jobs.store.scratch_path_for(operation.scratch, record.job_id))},
                )
                declared_command, _ = jobs.store.declared_launch(record.job_id)
                assert started["kind"] == "declared-operation"
                assert record.spec.timeout_seconds == 7200
                assert declared_command == expected
                assert systemd.started[0]["command"] == expected
                assert systemd.started[0]["timeout_seconds"] == 7200
            PY
            touch "$out"
          '';
      cachePushForegroundFixture =
        pkgs.runCommand "sinex-cache-push-foreground-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
            ];
          }
          ''
            fixture_bin="$TMPDIR/bin"
            mkdir -p "$fixture_bin"
            printf '#!%s\nprintf "%%s\\n" /nix/store/fixture-sinex-1\n' \
              ${pkgs.bash}/bin/bash > "$fixture_bin/nix"
            printf '#!%s\nprintf "%%s\\n" "$@" > "$CACHE_PUSH_ARGS"\nexit "''${CACHIX_EXIT:-0}"\n' \
              ${pkgs.bash}/bin/bash > "$fixture_bin/cachix"
            printf '#!%s\nexit 99\n' ${pkgs.bash}/bin/bash > "$fixture_bin/systemd-run"
            chmod +x "$fixture_bin/nix" "$fixture_bin/cachix" "$fixture_bin/systemd-run"
            export PATH="$fixture_bin:$PATH"
            export CACHE_PUSH_ARGS="$TMPDIR/cachix-args"
            ${pkgs.bash}/bin/bash ${../../scripts/sinnix-sinex-cache-push} --foreground /nix/store/fixture
            test "$(tr '\n' ' ' < "$CACHE_PUSH_ARGS")" = "push sinity /nix/store/fixture-sinex-1 "
            if CACHIX_EXIT=17 ${pkgs.bash}/bin/bash ${../../scripts/sinnix-sinex-cache-push} --foreground /nix/store/fixture; then
              echo "foreground cache-push failure was swallowed" >&2
              exit 1
            else
              test "$?" -eq 17
            fi
            touch "$out"
          '';
      cachePrebuildLifecycleFixture =
        pkgs.runCommand "sinex-cache-prebuild-lifecycle-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
            ];
          }
          ''
            fixture_bin="$TMPDIR/bin"
            flake_dir="$TMPDIR/flake"
            state_dir="$TMPDIR/state"
            mkdir -p "$fixture_bin" "$flake_dir"
            printf '%s\n' '{"nodes":{"sinex":{"locked":{"rev":"fixture-rev","url":"https://example.test/sinex"}}}}' \
              > "$flake_dir/flake.lock"
            printf '#!%s\nprintf "%%s\\n" /nix/store/fixture-sinex-1\n' \
              ${pkgs.bash}/bin/bash > "$fixture_bin/nix"
            printf '#!%s\nprintf "%%s\\n" "$@" > "$PREBUILD_PUSH_ARGS"\nexit "''${PUSH_EXIT:-0}"\n' \
              ${pkgs.bash}/bin/bash > "$fixture_bin/sinnix-sinex-cache-push"
            chmod +x "$fixture_bin/nix" "$fixture_bin/sinnix-sinex-cache-push"
            export PATH="$fixture_bin:$PATH"
            export PREBUILD_PUSH_ARGS="$TMPDIR/prebuild-push-args"
            ${pkgs.bash}/bin/bash ${../../scripts/sinnix-sinex-cache-prebuild} --flake-dir "$flake_dir" --state-dir "$state_dir"
            test "$(tr '\n' ' ' < "$PREBUILD_PUSH_ARGS")" = "--foreground /nix/store/fixture-sinex-1 "
            test "$(cat "$state_dir/last-built-rev")" = "fixture-rev"
            rm "$state_dir/last-built-rev"
            if PUSH_EXIT=19 ${pkgs.bash}/bin/bash ${../../scripts/sinnix-sinex-cache-prebuild} --flake-dir "$flake_dir" --state-dir "$state_dir"; then
              echo "prebuild reported success after a failed cache upload" >&2
              exit 1
            else
              test "$?" -eq 19
            fi
            test ! -e "$state_dir/last-built-rev"
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
      bdDoltAuthorityFixture =
        pkgs.runCommand "bd-dolt-authority-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.jq
              scriptRegistry.packageSet.beads
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${../../flake/tests/bd-dolt-authority.sh} ${scriptRegistry.packageSet.beads}/bin/bd
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
      chatgptConversationsFixture =
        pkgs.runCommand "chatgpt-conversations-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.nodejs
            ];
          }
          ''
            skill="$TMPDIR/chatgpt-conversations"
            mkdir -p "$skill/scripts"
            cp ${../../dots/_ai/skills/chatgpt-conversations/scripts/sinnix-chatgpt-conversations} "$skill/scripts/sinnix-chatgpt-conversations"
            cp ${../../dots/_ai/skills/chatgpt-conversations/tests.sh} "$skill/tests.sh"
            chmod -R u+w "$skill"
            ${pkgs.bash}/bin/bash "$skill/tests.sh"
            touch "$out"
          '';
      desktopCaptureFixture =
        pkgs.runCommand "desktop-capture-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            ocr="$TMPDIR/hyprland-ocr"
            dismiss="$TMPDIR/dismiss-scratchpads"
            toggle="$TMPDIR/toggle-scratch"
            cp ${../../scripts/hyprland-ocr} "$ocr"
            cp ${../../scripts/dismiss-scratchpads} "$dismiss"
            cp ${../../scripts/toggle-scratch} "$toggle"
            chmod +x "$ocr" "$dismiss" "$toggle"
            patchShebangs "$ocr" "$dismiss" "$toggle"
            ${pkgs.bash}/bin/bash ${../../flake/tests/desktop-capture.sh} "$ocr" "$dismiss" "$toggle"
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
            cp ${../../dots/_ai/skills/investigate/scripts/freeze.sh} "$freeze"
            cp ${../../dots/_ai/skills/investigate/scripts/recover-probe.sh} "$recover"
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
              # The explicit-model policy hook parses its structured payload
              # with python3.
              pkgs.python3
              pkgs.shellcheck
            ];
          }
          ''
            hooks="$TMPDIR/hooks"
            settings="$TMPDIR/settings.json"
            mkdir -p "$hooks"
            cp ${../../dots/claude/hooks}/*.sh "$hooks/"
            cp ${../../dots/claude/managed-settings.json} "$settings"
            chmod +x "$hooks"/*.sh
            patchShebangs "$hooks"
            ${pkgs.bash}/bin/bash ${../../flake/tests/hooks-harness.sh} "$hooks" "$settings"
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
        direnv-direct-commands = direnvDirectCommandsFixture;
        agentctl-operation-contract = agentctlOperationFixture;
        agentctl-operation-launch = agentctlOperationLaunchFixture;
        sinex-cache-push-foreground = cachePushForegroundFixture;
        sinex-cache-prebuild-lifecycle = cachePrebuildLifecycleFixture;
        preflight = preflightFixture;
        kitty-agent-here = kittyAgentHereFixture;
        bd-safety-hook = bdSafetyHookFixture;
        bd-dolt-authority = bdDoltAuthorityFixture;
        context-handoff = contextHandoffFixture;
        skill-authoring = skillAuthoringFixture;
        chatgpt-conversations = chatgptConversationsFixture;
        desktop-capture = desktopCaptureFixture;
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
