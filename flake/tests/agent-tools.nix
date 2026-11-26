# Agent CLI wrapper / MCP profile runtime checks (Claude, Codex, Pi, Hermes).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    {
      system,
      # The packaged binary, not a copy of the source with a hand-patched
      # shebang: the wrapper and the withPackages interpreter that discovery
      # builds are part of what these fixtures are testing, and a fixture that
      # rebuilds them itself passes while the real command is broken.
      sinnixScriptRegistry,
      ...
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sinexProbe = pkgs.writeShellScriptBin "sinexctl" ''
        printf '%s\n' "''${SINEX_TOKEN_FILE:-native-client-default}" "$SINEX_ENDPOINT" "$@"
      '';
      sinexLauncher =
        pkgs.writeScript "mcp-sinex-fixture"
          (import ../../modules/features/dev/agents/mcp-tools.nix {
            inherit lib pkgs inputs;
            scriptPkgs = { };
            config.services.sinex = {
              package = sinexProbe;
              stateDir = "/var/lib/fixture/current-generation";
            };
          }).mcpSinexText;
      headlessSinexLauncher =
        pkgs.writeScript "mcp-sinex-headless-fixture"
          (import ../../modules/features/dev/agents/mcp-tools.nix {
            inherit lib pkgs;
            inputs.sinex.packages.${system}.sinexctl = sinexProbe;
            scriptPkgs = { };
            config = { };
          }).mcpSinexText;
      sinexMcpBinding = pkgs.runCommand "sinex-mcp-binding" { } ''
        env -u SINEX_TOKEN_FILE -u SINEX_ENDPOINT ${sinexLauncher} fixture-argument > actual
        printf '%s\n' /var/lib/fixture/current-generation/tokens/agent.token \
          http://127.0.0.1:7171 mcp fixture-argument > expected
        cmp expected actual
        SINEX_TOKEN_FILE=/fixture/explicit.token SINEX_ENDPOINT=unix:/fixture/explicit.sock \
          ${sinexLauncher} explicit-argument > actual
        printf '%s\n' /fixture/explicit.token unix:/fixture/explicit.sock \
          mcp explicit-argument > expected
        cmp expected actual
        env -u SINEX_TOKEN_FILE -u SINEX_ENDPOINT ${headlessSinexLauncher} --help > actual
        printf '%s\n' native-client-default http://127.0.0.1:7171 mcp --help > expected
        cmp expected actual
        touch "$out"
      '';
      polylogueSentinelDataDir = "/tmp/sinnix-polylogue-agent-tools-sentinel";
      runtimeDefaults = import ../data/runtime-defaults.nix { inherit lib; };
      mcpRegistry = import ../data/mcp-registry.nix { inherit lib; };
      agentProfiles = import ../data/agent-profiles.nix;
      # Derived from the profile registry rather than hand-listed: every declared
      # profile must produce an installed wrapper, and adding or retiring a profile
      # must not require editing this file in several places.
      piPresetNames = map (name: lib.removeSuffix ".json" name) (
        lib.filter (name: lib.hasSuffix ".json" name) (
          lib.attrNames (builtins.readDir ../../dots/pi/presets)
        )
      );
      laneWrapperFiles = map (binName: ".local/bin/${binName}") (
        (map (profile: profile.binName) (lib.attrValues agentProfiles.claudeProfiles))
        ++ (map (profile: profile.binName) (lib.attrValues agentProfiles.codexProfiles))
        ++ (map (name: "hermes-${name}") (lib.attrNames agentProfiles.hermesProfiles))
        ++ [ "pi" ]
        ++ (map (name: "pi-${name}") piPresetNames)
      );
      # Each profile's wrapper must honour the registry entry it was rendered
      # from: the MCP config file its profile selects and the profile marker
      # the hooks branch on. Derived here so a profile rename needs no edit in
      # this file, and so a wrapper that stops following the registry fails
      # rather than a literal that only this test and the renderer know.
      claudeLaneWrapperChecks = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (
          _: profile:
          let
            wrapper = ''"$HOME/.local/bin/${profile.binName}"'';
            mcpFile = "mcp";
          in
          ''
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/${mcpFile}.json"' ${wrapper}
            grep -Fq 'export SINNIX_CLAUDE_PROFILE=${profile.mcpProfile}' ${wrapper}
            grep -Fq 'export CLAUDE_CONFIG_DIR="''${CLAUDE_CONFIG_DIR:-$HOME/.config/claude}"' ${wrapper}
          ''
        ) agentProfiles.claudeProfiles
      );
      codexLaneWrapperChecks = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (_: profile: ''
          grep -Fq 'exec "$STATE/npm/bin/codex" "$@"' "$HOME/.local/bin/${profile.binName}"
        '') agentProfiles.codexProfiles
      );
      expectedProfileServers =
        client: profiles:
        builtins.toJSON (
          lib.genAttrs profiles (
            profile: lib.attrNames (mcpRegistry.selectClientServersForProfile profile client)
          )
        );
      expectedClaudeProfileServersJson = expectedProfileServers "claude" [
        "default"
      ];
      expectedCodexProfileServersJson = expectedProfileServers "codex" [
        "default"
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
            sinnix.services.polylogue.liveRoot = polylogueSentinelDataDir;
          })
        ];
        assertions =
          config:
          let
            hm = config.home-manager.users.${config.sinnix.user.name};
            codexWrapperText = hm.home.file.".local/bin/codex".text or "";
          in
          [
            {
              assertion = !(builtins.elem ".claude.json" config.sinnix.persistence.home.files);
              message = "Claude's atomically replaced global JSON must not be a single-file bind mount.";
            }
            {
              assertion =
                (hm.home.sessionVariables.CLAUDE_CONFIG_DIR or null) == "${hm.home.homeDirectory}/.config/claude";
              message = "Claude global config must live inside its persisted directory.";
            }
            {
              assertion = !(hm.xdg.configFile ? "claude/settings.json");
              message = "Claude settings.json must not be managed through Home Manager xdg.configFile.";
            }
            {
              assertion = lib.hasInfix "export PATH=\"$HOME/.local/bin:" codexWrapperText;
              message = "the Codex wrapper must resolve nested codex calls through ~/.local/bin before its private npm prefix";
            }
            {
              assertion = builtins.hasAttr ".config/claude/agents" hm.home.file;
              message = "Claude agent definitions must be linked as one directory from the shared dots tree.";
            }
            {
              assertion =
                (config.environment.etc."codex/config.toml".source or null)
                == config.sinnix.features.dev.mcp-servers.codexConfigSource;
              message = "Codex defaults and MCP servers must share the generated system config.";
            }
            {
              assertion = lib.all (rule: builtins.elem rule config.systemd.tmpfiles.rules) [
                "d /realm/state/codex 0700 ${config.sinnix.user.name} users -"
                "d /realm/state/codex/logs 0700 ${config.sinnix.user.name} users -"
                "d /realm/state/codex/home 0700 ${config.sinnix.user.name} users -"
                "d /realm/state/codex/sqlite 0700 ${config.sinnix.user.name} users -"
                "h /realm/state/codex/sqlite - - - - +C"
              ];
              message = "Codex home, SQLite state and logs must have private, user-owned Realm directories.";
            }
            {
              assertion =
                (config.fileSystems."/home/${config.sinnix.user.name}/.codex".device or null)
                == "/realm/state/codex/home";
              message = "Codex home must be bound from Realm, off the root SSD.";
            }
            {
              assertion =
                let
                  # Every role the Codex config names, read from the config
                  # itself rather than restated here.
                  roleFiles = lib.mapAttrsToList (_: role: role.config_file) (
                    lib.filterAttrs (_: role: builtins.isAttrs role && role ? config_file)
                      (builtins.fromTOML (builtins.readFile ../../dots/codex/config.toml)).agents
                  );
                in
                roleFiles != [ ]
                && builtins.all (
                  file:
                  (config.environment.etc."codex/${file}".source or null)
                  == "${config.sinnix.paths.dotsRoot}/codex/${file}"
                  && builtins.pathExists (../../dots/codex + "/${file}")
                  && builtins.hasAttr ".codex/${file}" hm.home.file
                ) roleFiles;
              message = "Every agent role in dots/codex/config.toml must exist and resolve beside the system Codex config and in the Codex home through a live dots link.";
            }
            {
              assertion =
                (config.environment.etc."codex/hooks.json".source or null)
                == config.sinnix.features.dev.mcp-servers.codexHooksSource
                && !(hm.home.file ? ".codex/hooks.json");
              message = "Codex hooks must load from the system layer alone: there they are managed policy, and a second copy in the Codex home would run every hook twice once trusted.";
            }
            {
              assertion = builtins.hasAttr ".agents/skills" hm.home.file;
              message = "Native Codex skill discovery must link ~/.agents/skills to the live shared root.";
            }
            {
              assertion =
                let
                  skillsActivation = hm.home.activation.codexSkills.data or "";
                in
                lib.hasInfix "run rm" skillsActivation
                && lib.hasInfix "run mkdir" skillsActivation
                && lib.hasInfix "run ln" skillsActivation
                && !(lib.hasInfix "\n                      rm " skillsActivation);
              message = "Codex skill linking must route every mutation through Home Manager's dry-run-aware run helper.";
            }
            {
              assertion = builtins.all (path: builtins.hasAttr path hm.home.file) [
                ".local/bin/sinnix-chrome-control"
                ".local/bin/sinnix-hypr-control"
                ".local/bin/sinnix-keyboard-control"
                ".local/bin/sinnix-kitty-control"
                ".local/bin/sinnix-screenshot-control"
              ];
              message = "Agent control helpers must be installed through Home Manager.";
            }
          ];
      };
      agentToolsFixture = {
        evaluated = agentToolsRuntimeEvaluated;
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
          ".local/bin/hermes"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-polylogue"
          ".local/bin/mcp-sinex"
          ".config/hermes/skills"
          ".config/claude/agents"
          ".agents/skills"
          ".codex/agents/explorer.toml"
          ".codex/agents/implementer.toml"
          ".codex/agents/review.toml"
        ];
        fixtureAssets = [
          {
            target = ".local/bin/sinnix-chrome-control";
            source = ../../dots/_ai/skills/desktop-control/scripts/chrome-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-hypr-control";
            source = ../../dots/_ai/skills/desktop-control/scripts/hypr-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-keyboard-control";
            source = ../../dots/_ai/skills/desktop-control/scripts/keyboard-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-kitty-control";
            source = ../../dots/_ai/skills/desktop-control/scripts/kitty-remote-control.sh;
            executable = true;
          }
          {
            target = ".local/bin/sinnix-screenshot-control";
            source = ../../dots/_ai/skills/desktop-control/scripts/screenshot-color-lab.sh;
            executable = true;
          }

        ];
        xdgConfigFiles = [
          "claude/mcp.json"
          "claude/skills"
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
      agentToolsRuntimeEvaluated = evalTestSpec system devAgentToolsRuntimeSpec;
      agentToolsRuntimeConfig = agentToolsRuntimeEvaluated.config;
      agentToolsCodexConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexConfigSource;
      agentToolsHermesConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.agentTools.hermesConfigSource;
      agentToolsHermesProfileConfigSources =
        agentToolsRuntimeConfig.sinnix.features.dev.agentTools.hermesProfileConfigSources;
      agentToolsCodexSkillsActivation = pkgs.writeText "codex-skills-activation.sh" (
        agentToolsRuntimeConfig.home-manager.users.${agentToolsRuntimeConfig.sinnix.user.name}.home.activation.codexSkills.data
      );
      agentToolsPiSources = agentToolsRuntimeConfig.sinnix.features.dev.agentTools.piSources;
      agentToolsPiActivation = pkgs.writeText "pi-config-activation.sh" (
        agentToolsRuntimeConfig.home-manager.users.${agentToolsRuntimeConfig.sinnix.user.name}.home.activation.piConfig.data
      );
      piPackage = inputs.pi.packages.${system}.pi;
      agentToolsClaudeStateActivation = pkgs.writeText "claude-state-activation.sh" (
        agentToolsRuntimeConfig.home-manager.users.${agentToolsRuntimeConfig.sinnix.user.name}.home.activation.claudeSymlink.data
      );

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
          # "12G" -> bytes, so the hierarchy asserts below compare magnitudes
          # rather than spellings.
          sliceBytes =
            value:
            let
              unit = lib.substring (lib.stringLength value - 1) 1 value;
              number = lib.toInt (lib.substring 0 (lib.stringLength value - 1) value);
              scale =
                {
                  K = 1024;
                  M = 1024 * 1024;
                  G = 1024 * 1024 * 1024;
                }
                .${unit};
            in
            number * scale;
          budget = userSlices.agent;
          hostBudget = runtimeDefaults.memoryBudget;
          managedWork = userSlices.agent-ctl;
          poolSlices = lib.genAttrs [
            "agent-ctl-agent"
            "agent-ctl-pytest"
            "agent-ctl-pytest-heavy"
            "agent-ctl-pytest-quick"
            "agent-ctl-bulk"
            "agent-ctl-normal"
            "agent-ctl-interactive"
            "agent-ctl-shell"
            "agent-ctl-shell-quick"
            "agent-ctl-shell-long"
            "agent-ctl-background"
            "agent-ctl-measure"
            "agent-ctl-system-build"
            "agent-ctl-compile"
            "agent-ctl-codex"
          ] (name: userSlices.${name});
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
          declaredPools = agentToolsRuntimeConfig.sinnix.services.agentctl.pools;
        in
        # The gateway's shell.run pools (sinnix_agent_gateway/shell_pools.py)
        # are declared pools with their own slices.
        assert lib.assertMsg (
          declaredPools ? shell-quick
          && declaredPools ? shell-long
          && poolSlices ? agent-ctl-shell-quick
          && poolSlices ? agent-ctl-shell-long
        ) "the gateway shell.run groups must be declared agentctl pools with slices";
        assert lib.assertMsg (
          declaredPools ? background && poolSlices ? agent-ctl-background
        ) "the offload pool must be declared with its low-weight slice";
        # Benchmarks and system builds never occupy the bulk slots checks use.
        assert lib.assertMsg (
          declaredPools.measure.parallel == 1 && declaredPools.system-build.parallel == 1
        ) "measurements and system builds each run in a one-slot pool of their own";
        assert lib.assertMsg (
          declaredPools ? compile && poolSlices ? agent-ctl-compile
        ) "type and lint checks have a pool and slice of their own";
        # The job plane holds one test build beside one check.
        assert lib.assertMsg (
          declaredPools.normal.parallel == 1 && declaredPools.compile.parallel == 1
        ) "normal and compile each admit one Cargo build";
        assert lib.assertMsg (lib.all (token: !(lib.hasInfix token avoidPattern))
          forbiddenAvoidTokens
        ) "the earlyoom fallback must not exempt agents, browsers, runtimes, or generic shells";
        assert lib.assertMsg
          (
            # Agent work's runaway-prone slices each fit, with the kernel
            # reserve, the zram store and every protected line of the host
            # budget, in physical memory; the sessions have no ceiling; and
            # the desktop's guarantee in that budget is the one its slices
            # carry.
            lib.all (name: userSlices ? ${name}) [
              "agent-cli"
              "agent-tool"
              "agent-ctl"
            ]
            && budget.CPUWeight < userSlices.app.CPUWeight
            && budget.IOWeight * 10 <= userSlices.app.IOWeight
            && budget ? CPUQuota
            && !(budget ? MemoryMax)
            && !(budget ? MemoryHigh)
            && !(budget ? MemorySwapMax)
            && budget ? TasksMax
            && !(budget ? ManagedOOMMemoryPressure)
            && !(budget ? ManagedOOMSwap)
            &&
              lib.max (sliceBytes managedWork.MemoryMax) (sliceBytes userSlices.agent-tool.MemoryMax)
              + (hostBudget.kernel + hostBudget.zram + hostBudget.protected) * 1024 * 1024
              <= hostBudget.ram * 1024 * 1024
            && hostBudget.desktop * 1024 * 1024 == sliceBytes runtimeDefaults.slices.system.user.MemoryMin
            # The desktop's guarantee is hard, and every ancestor carries it.
            && userSlices.desktop.MemoryMin == userSlices.desktop-shell.MemoryMin
            &&
              sliceBytes runtimeDefaults.slices.system.user.MemoryMin == sliceBytes userSlices.app.MemoryMin
              + sliceBytes userSlices.session.MemoryMin
              + sliceBytes userSlices.desktop.MemoryMin
            && managedWork.CPUWeight < userSlices.app.CPUWeight
            && !(managedWork ? MemoryHigh)
            && !(userSlices.agent-tool ? MemoryHigh)
            && managedWork.ManagedOOMSwap == "kill"
            && managedWork.ManagedOOMMemoryPressure == "kill"
            && managedWork.ManagedOOMMemoryPressureLimit == "40%"
            && managedWork.ManagedOOMMemoryPressureDurationSec == "15s"
            && userSlices.agent-tool.ManagedOOMSwap == "kill"
            && userSlices.agent-tool.ManagedOOMMemoryPressure == "kill"
            # These trees have no monitored ancestor either: no oomd candidate
            # may contain the coordinator or basic desktop interactivity.
            &&
              lib.all
                (name: !(userSlices.${name} ? ManagedOOMMemoryPressure) && !(userSlices.${name} ? ManagedOOMSwap))
                [
                  "agent-cli"
                  "app"
                  "session"
                  "desktop"
                  "desktop-shell"
                ]
            # Interactive agents are protected and never capped, throttled
            # or given a pressure kill that would take the coordinator.
            && userSlices.agent-cli ? MemoryLow
            && !(userSlices.agent-cli ? MemoryHigh)
            && !(userSlices.agent-cli ? MemoryMax)
            && !(userSlices.agent-cli ? MemorySwapMax)
            && !(userSlices.agent-cli ? ManagedOOMMemoryPressure)
            && userSlices.agent-cli.CPUWeight > userSlices.agent-tool.CPUWeight
            && !(poolSlices.agent-ctl-agent ? ManagedOOMPreference)
            && !(poolSlices.agent-ctl-agent ? ManagedOOMMemoryPressure)
            && !(poolSlices.agent-ctl-agent ? ManagedOOMSwap)
            # No extra pytest-parent trigger; plane-wide monitoring still
            # makes every eligible test job a candidate under sustained thrash.
            && !(poolSlices.agent-ctl-pytest ? ManagedOOMMemoryPressure)
            && poolSlices.agent-ctl-pytest.CPUWeight == 200
            && poolSlices.agent-ctl-pytest.IOWeight == 200
            # A pool sets a memory limit only where it is tighter than the
            # plane's, and throttles below its own ceiling.
            && lib.all (
              slice:
              !(slice ? MemoryMax)
              || (
                sliceBytes slice.MemoryMax <= sliceBytes managedWork.MemoryMax
                && sliceBytes slice.MemoryHigh < sliceBytes slice.MemoryMax
              )
            ) (lib.attrValues poolSlices)
            && poolSlices.agent-ctl-pytest-heavy.ManagedOOMMemoryPressure == "kill"
            && poolSlices.agent-ctl-pytest-heavy.CPUWeight == 200
            && poolSlices.agent-ctl-pytest-heavy.IOWeight == 200
            && !(poolSlices.agent-ctl-bulk ? IOReadBandwidthMax)
            # Every pool's swap fits inside the plane's.
            && lib.all (slice: sliceBytes slice.MemorySwapMax <= sliceBytes managedWork.MemorySwapMax) (
              lib.attrValues poolSlices
            )
            && poolSlices.agent-ctl-bulk.ManagedOOMMemoryPressure == "kill"
            && poolSlices.agent-ctl-bulk.CPUWeight == 20
            && poolSlices.agent-ctl-bulk.IOWeight == 10
            # Offloads yield the disk to every other job pool.
            && lib.all (slice: poolSlices.agent-ctl-background.IOWeight < slice.IOWeight) (
              lib.attrValues (removeAttrs poolSlices [ "agent-ctl-background" ])
            )
            && lib.all (slice: slice.IOAccounting == true) (lib.attrValues poolSlices)
          )
          "agentctl coordinator work must yield to protected interactive slices; pool slices own fixed caps";
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
              pkgs.nodejs_22
              pkgs.gnutar
              pkgs.gzip
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
            test "$#" = 5
            test "$1" = ci
            test "$2" = --prefix
            test "$4" = --global=false
            test "$5" = --omit=dev
            test -f "$3/npm-shrinkwrap.json"
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

            mkdir -p "$3/bin"
            cat > "$3/bin/fakeagent" <<'AGENT'
            #!${pkgs.bash}/bin/bash
            printf 'fakeagent 1.0\n'
            AGENT
            chmod +x "$3/bin/fakeagent"
            EOF
            chmod +x "$TMPDIR/bin/npm"

            runtime_path="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.bash
                pkgs.coreutils
                pkgs.util-linux
                pkgs.nodejs_22
                pkgs.gnutar
                pkgs.gzip
              ]
            }"
            mkdir "$TMPDIR/package"
            cat > "$TMPDIR/package/package.json" <<'JSON'
            {"name":"@example/fake-cli","version":"1.0.0","bin":{"fakeagent":"bin/fakeagent"}}
            JSON
            cat > "$TMPDIR/package/npm-shrinkwrap.json" <<'JSON'
            {"name":"@example/fake-cli","version":"1.0.0","lockfileVersion":3,"packages":{"":{"name":"@example/fake-cli","version":"1.0.0"}}}
            JSON
            tar -czf "$TMPDIR/locked-package.tgz" -C "$TMPDIR" package
            bootstrap=${../../scripts/sinnix-agent-npm-bootstrap}
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path" "$TMPDIR/locked-package.tgz" &
            first=$!
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path" "$TMPDIR/locked-package.tgz" &
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
            ${pkgs.bash}/bin/bash "$bootstrap" fake-agent @example/fake-cli fakeagent "$runtime_path" "$TMPDIR/absent-package.tgz"
            test "$(cat "$HOME/npm-invocations")" = 1
            test -d "$package_parent/.fake-cli-Keep1234"
            test ! -e "$HOME/.local/state/fake-agent/launch.sh"
            test "$("$state/bin/fakeagent" --version)" = "fakeagent 1.0"
            touch "$out"
          '';

      # Provably fails when: the wrapper renderer stops following the profile
      # registry (verified by hardcoding MCP_CONFIG to mcp.json in
      # backends.nix, which breaks every non-full profile), a rendered MCP
      # profile's server set diverges from the registry's own selection, a
      # Hermes profile gains a toolset its capability boundary forbids.
      #
      # Note: changing flake/data/agent-profiles.nix alone does NOT fail this
      # check, and should not -- both the renderer and these expectations
      # derive from that registry, which is the point.
      devAgentToolsRuntime = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-runtime-check";
          nativeBuildInputs = builtins.filter (pkg: pkg != pkgs.expect) agentToolsFixture.nativeBuildInputs;
          setup = agentToolsFixture.setup + ''
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
            ${pkgs.python3}/bin/python - <<'PY'
            import tomllib
            from pathlib import Path

            config = tomllib.loads(Path("${agentToolsCodexConfigSource}").read_text())
            assert "model_catalog_json" not in config
            assert config["features"]["multi_agent_v2"] is True
            PY
          '';
          script = ''
            trap 'echo "dev-agent-tools-runtime failed at line $LINENO" >&2' ERR
            # mkHmRuntimeCheck renders declared files but deliberately does
            # not execute Home Manager activation. Exercise the Claude state
            # step here with the same `run` contract used by activation:
            # settings.json is seeded once as a private file and ~/.claude
            # points at the config directory.
            claude_home="$TMPDIR/claude-state"
            mkdir -p "$claude_home"
            (
              export HOME="$claude_home"
              run() { "$@"; }
              source ${agentToolsClaudeStateActivation}
            )
            cmp "$claude_home/.config/claude/settings.json" ${../../dots/claude/settings-seed.json}
            test "$(stat -c '%a' "$claude_home/.config/claude/settings.json")" = 600
            test "$(readlink "$claude_home/.claude")" = .config/claude
            printf '{"model": "kept"}\n' > "$claude_home/.config/claude/settings.json"
            (
              export HOME="$claude_home"
              run() { "$@"; }
              source ${agentToolsClaudeStateActivation}
            )
            grep -Fq '"kept"' "$claude_home/.config/claude/settings.json"

            test -L "$HOME/.agents/skills"
            # The live checkout is intentionally absent from the Nix sandbox;
            # resolve the declared link without requiring its target to exist.
            test "$(readlink -m "$HOME/.agents/skills")" = ${agentToolsRuntimeConfig.sinnix.paths.dotsRoot}/_ai/skills
            test -L "$HOME/.config/claude/skills"
            test "$(readlink -m "$HOME/.config/claude/skills")" = ${agentToolsRuntimeConfig.sinnix.paths.dotsRoot}/_ai/skills
            # Home Manager's dry-run helper must be the sole mutation path for
            # the skill links. It must neither replace existing app state nor
            # create its declared links in a synthetic home.
            dry_home="$TMPDIR/codex-skills-dry-run"
            mkdir -p "$dry_home/.codex/skills"
            touch "$dry_home/.codex/skills/app-installed-skill"
            # A link to a declared skill that no longer exists.
            ln -s ${agentToolsRuntimeConfig.sinnix.paths.dotsRoot}/_ai/skills/retired-skill "$dry_home/.codex/skills/retired-skill"
            ln -s /private/owner/skill "$dry_home/.codex/skills/private-skill"
            (
              export HOME="$dry_home"
              run() { :; }
              source ${agentToolsCodexSkillsActivation}
            )
            test -f "$dry_home/.codex/skills/app-installed-skill"
            test -L "$dry_home/.codex/skills/retired-skill"
            (
              export HOME="$dry_home"
              run() { "$@"; }
              source ${agentToolsCodexSkillsActivation}
            )
            test ! -L "$dry_home/.codex/skills/retired-skill"
            test -L "$dry_home/.codex/skills/private-skill"
            test -f "$dry_home/.codex/skills/app-installed-skill"
            test -L "$HOME/.config/claude/mcp.json"
            test -L "$HOME/.config/hermes/skills"
            python3 - "$HOME/.hermes/config.yaml" <<'PYCODE'
            import pathlib, re, sys
            config = pathlib.Path(sys.argv[1]).read_text()
            assert 'provider: openai-codex' in config
            assert 'provider: gemini' in config
            assert 'mcp_servers:' in config
            for name in ('context7', 'github', 'lynchpin', 'sinex'):
                assert f'{name}:' in config, name
            assert 'external_dirs:' in config
            assert 'observability/nemo_relay' in config
            assert 'approvals:' in config
            assert re.search(r"mode: ['\"]off['\"]", config)
            local_profile = (pathlib.Path.home() / '.hermes/profiles/local/config.yaml').read_text()
            assert 'provider: custom' in local_profile
            for profile, required, forbidden in (
                ('research', ('web', 'browser', 'delegation'), ('terminal',)),
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
            PYCODE

            for wrapper in \
              ${lib.concatMapStringsSep " \\\n              " (f: ''"$HOME/${f}"'') laneWrapperFiles} \
              "$HOME/.local/bin/pi" \
              "$HOME/.local/bin/hermes"; do
              test -x "$wrapper"
              bash -n "$wrapper"
            done

            jq -e '
              (has("mcpServers") | not) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("sessionstart-context.sh"))) and
              ([.hooks.Stop[].hooks[].command]
                | any(. == "polylogue internal hook Stop"))
            ' ${
              agentToolsRuntimeEvaluated.config.environment.etc."claude-code/managed-settings.json".source
            } >/dev/null
            cmp ${
              agentToolsRuntimeEvaluated.config.environment.etc."claude-code/managed-settings.json".source
            } ${inputs.self}/dots/claude/managed-settings.json

            # Rendered profile configs must match the registry's own computed
            # selection -- membership is derived from mcp-registry.nix at eval
            # time, never frozen as literals.
            for pair in \
              "mcp.json default"; do
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

            system_config = tomllib.loads(pathlib.Path('${agentToolsCodexConfigSource}').read_text())
            assert system_config['features']['hooks'] is True
            assert system_config['log_dir'] == '/realm/state/codex/logs'
            assert system_config['sqlite_home'] == '/realm/state/codex/sqlite'

            default = set(system_config['mcp_servers'])
            import json
            expected = json.loads('${expectedCodexProfileServersJson}')
            assert default == set(expected['default'])
            PYCODE

            jq -e '
              [.hooks.Stop[].hooks[].command]
              | any(. == "polylogue internal hook Stop --harness codex")
            ' ${agentToolsRuntimeEvaluated.config.environment.etc."codex/hooks.json".source} >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | any(contains("sessionstart-context.sh"))
            ' ${agentToolsRuntimeEvaluated.config.environment.etc."codex/hooks.json".source} >/dev/null
            ${claudeLaneWrapperChecks}
            grep -Fq 'claude_args+=(--add-dir=' "$HOME/.local/bin/claude"
            ${codexLaneWrapperChecks}

            # Every outer agent wrapper must enter agent-cli.slice before its
            # bootstrap runs. A missing scope launch leaves npm/bootstrap work
            # in the terminal session and makes the cgroup regression invisible
            # to admission. The containment pattern is asserted verbatim so
            # the shipped wrapper and the guard exercised by the
            # agent-scope-guard fixture cannot diverge.
            for wrapper in \
              "$HOME/.local/bin/claude" \
              "$HOME/.local/bin/codex"; do
              grep -Fq 'npm/bin/' "$wrapper"
              grep -Fq 'exec "$STATE/npm/bin/' "$wrapper"
            done
            for wrapper in \
              "$HOME/.local/bin/claude" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/pi"; do
              grep -Fq '/proc/self/cgroup' "$wrapper"
              grep -Fq -- '--slice=agent-cli.slice' "$wrapper"
              grep -Fq -- '${runtimeDefaults.agentContainedCasePattern}' "$wrapper"
            done
            if grep -R 'MemoryHigh\|MemoryMax\|MemorySwapMax' "$HOME/.local/bin/claude" "$HOME/.local/bin/codex" "$HOME/.local/bin/pi"; then
              echo "agent wrappers must not hardcode resource limits" >&2
              exit 1
            fi
            for wrapper in "$HOME/.local/bin/claude" "$HOME/.local/bin/codex"; do
              grep -Fq 'sinnix-agent-npm-bootstrap' "$wrapper"
              grep -Fq 'export npm_config_prefix="$STATE/npm"' "$wrapper"
              grep -Fq 'export NPM_CONFIG_PREFIX="$STATE/npm"' "$wrapper"
              grep -Fq 'export PATH=' "$wrapper"
            done
            grep -Fq '@anthropic-ai/claude-code' "$HOME/.local/bin/claude"
            grep -Fq '@openai/codex' "$HOME/.local/bin/codex"

            # Pi runs the pinned upstream package with the caller's arguments
            # and nothing else: its provider, instructions and packages come
            # from the settings and links checked below.
            grep -Fxq 'exec ${piPackage}/bin/pi "$@"' "$HOME/.local/bin/pi"
            grep -Fq 'source ${agentToolsPiSources.unsetProviderKeys}' "$HOME/.local/bin/pi"
            grep -Fq 'export TMPDIR=' "$HOME/.local/bin/pi"
            grep -Fq 'PI_CLAUDE_CODE_COMMAND="$HOME/.local/state/claude-code/npm/bin/claude"' "$HOME/.local/bin/pi"

            # No key pi's own source reads from the environment survives the
            # launcher, so no provider is selected by an ambient key. The
            # names come from the pinned source, so a release that reads a
            # new one fails here until the launcher removes it.
            pi_key_names="$(grep -oE '"[A-Z][A-Z0-9_]*(API_KEY|TOKEN)[A-Z0-9_]*"' \
              ${inputs.pi}/packages/ai/src/env-api-keys.ts | tr -d '"' | sort -u)"
            test "$(wc -l <<<"$pi_key_names")" -ge 40
            (
              for name in $pi_key_names AWS_PROFILE AWS_ACCESS_KEY_ID EXA_API_KEY; do
                export "$name=stray"
              done
              export CONTEXT7_API_KEY=kept GITHUB_TOKEN=kept
              source ${agentToolsPiSources.unsetProviderKeys}
              for name in $pi_key_names AWS_PROFILE AWS_ACCESS_KEY_ID EXA_API_KEY; do
                if [ -n "''${!name:-}" ]; then
                  echo "pi launcher leaves $name in the environment" >&2
                  exit 1
                fi
              done
              test "$CONTEXT7_API_KEY" = kept
              test "$GITHUB_TOKEN" = kept
            )

            # The tool-server file lists exactly the registry's servers for
            # pi, each found by search instead of declared up front.
            rendered="$(jq -r '.mcpServers | keys | sort | join(",")' ${agentToolsPiSources.mcpConfigFile})"
            test "$rendered" = '${lib.concatStringsSep "," (lib.attrNames (mcpRegistry.selectClientServersForProfile "default" "pi"))}'
            jq -e '
              (.mcpServers | length) >= 4 and
              ([.mcpServers[] | .exposure] | all(. == "deferred")) and
              ([.mcpServers[] | .description | length > 0] | all) and
              .mcpServers.github.command == "mcp-github" and
              (.mcpServers.context7.url | startswith("https://"))
            ' ${agentToolsPiSources.mcpConfigFile} >/dev/null

            # Declared settings: the ChatGPT sign-in as default, Sinnix's own
            # package first and read from the checkout, the rest store paths.
            jq -e --arg own ${agentToolsRuntimeConfig.sinnix.paths.dotsRoot}/pi '
              .defaultProvider == "openai" and
              (.defaultModel | length > 0) and
              .enableInstallTelemetry == false and
              .packages[0] == $own and
              (.packages[1:] | length) >= 5 and
              ([.packages[1:][] | if type == "object" then .source else . end
                | startswith("/nix/store/")] | all) and
              ([.packages[] | objects | select(.source | endswith("@plannotator/pi-extension")) | .skills == []] == [true])
            ' ${agentToolsPiSources.settingsFile} >/dev/null
            for package in $(jq -r '.packages[1:][] | if type == "object" then .source else . end' ${agentToolsPiSources.settingsFile}); do
              test -e "$package"
            done

            # Activation links the instructions and tool servers and merges
            # the declared settings over pi's own keys without losing them.
            pi_home="$TMPDIR/pi-state"
            mkdir -p "$pi_home/.pi/agent"
            printf '{"deviceId": "kept", "defaultProvider": "deepseek", "packages": ["npm:stale"]}\n' \
              > "$pi_home/.pi/agent/settings.json"
            (
              export HOME="$pi_home"
              run() { "$@"; }
              source ${agentToolsPiActivation}
            )
            jq -e --slurpfile declared ${agentToolsPiSources.settingsFile} '
              .deviceId == "kept" and
              .defaultProvider == "openai" and
              .packages == $declared[0].packages
            ' "$pi_home/.pi/agent/settings.json" >/dev/null
            test "$(stat -c '%a' "$pi_home/.pi/agent/settings.json")" = 600
            test "$(readlink "$pi_home/.pi/agent/AGENTS.md")" = "$pi_home/.config/claude/CLAUDE.md"
            test "$(readlink "$pi_home/.pi/agent/mcp.json")" = ${agentToolsPiSources.mcpConfigFile}
            rm "$pi_home/.pi/agent/settings.json"
            (
              export HOME="$pi_home"
              run() { "$@"; }
              source ${agentToolsPiActivation}
            )
            cmp "$pi_home/.pi/agent/settings.json" ${agentToolsPiSources.settingsFile}
            grep -Fq 'npm ci --prefix "$staged" --global=false --omit=dev' '${../../scripts/sinnix-agent-npm-bootstrap}'
            grep -Fq 'export npm_config_prefix="$STATE/npm"' '${../../scripts/sinnix-agent-npm-bootstrap}'

            "$HOME/.local/bin/mcp-polylogue" --help > mcp-polylogue-help
            grep -q 'MCP' mcp-polylogue-help
            SINEX_TOKEN_FILE="$HOME/synthetic-agent.token" \
              "$HOME/.local/bin/mcp-sinex" --help > mcp-sinex-help
            grep -q 'mcp' mcp-sinex-help
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
      # The agent wrappers' scope decision, exercised against cgroup paths
      # taken from this host rather than re-asserted as wrapper text. A queued
      # task's scope is the boundary that carries the lane's MemoryMax and the
      # cancellation reap, so an agent started inside one must stay in it,
      # while an agent started from a terminal must still be moved.
      agentScopeGuardFixture =
        pkgs.runCommand "agent-scope-guard-fixture"
          {
            nativeBuildInputs = [ pkgs.bash ];
          }
          ''
            cat > guard.sh <<'GUARD'
            case "$1" in
              ${runtimeDefaults.agentContainedCasePattern}) echo contained ;;
              *) echo reexec ;;
            esac
            GUARD

            expect() {
              actual="$(${pkgs.bash}/bin/bash guard.sh "$2")"
              if [ "$actual" != "$1" ]; then
                echo "agent scope guard: expected $1 for $2, got $actual" >&2
                exit 1
              fi
            }

            user=/user.slice/user-1000.slice/user@1000.service

            # A lane's queued task: the service that owns its MemoryMax.
            ctl=$user/agent.slice/agent-ctl.slice
            expect contained "0::$ctl/agent-ctl-agent.slice/agentctl-agent-sinnix-lane-sinnix-5ntw-9b15d371.service"
            # A pool scope systemd named, rather than one named for a launch input.
            expect contained "0::$ctl/agent-ctl-agent.slice/run-p988139-i193814380.scope"
            # A pool other than agent still bounds what it launches.
            expect contained "0::$ctl/agent-ctl-normal.slice/run-p491309-i193318106.scope"
            expect contained "0::$ctl/agent-ctl-work.slice/pueued.service"
            expect contained "0::$user/agent.slice/agent-cli.slice/run-p1088598-i193914838.scope"
            # An agent started by a tool command joins the CLI slice.
            expect reexec "0::$user/agent.slice/agent-tool.slice/agent-tool-1449245.scope"

            # An interactive launch from a terminal has no boundary yet.
            expect reexec "0::$user/session.slice/kitty-52885-22.scope"
            expect reexec "0::$user/app.slice/app-chromium.scope"
            expect reexec "0::/system.slice/system-critical.slice/sshd.service"
            # Separator discipline: a slice merely ending in a contained name
            # is a different slice with a different budget.
            expect reexec "0::$user/app.slice/app-agent.slice/app-agent-stub.scope"
            expect reexec "0::$user/app.slice/app-agentctl.slice/app-agentctl-stub.scope"
            expect reexec "0::$user/app.slice/app-agent-cli.slice/app-agent-cli-stub.scope"

            # Which invocations are agent sessions, from the rendered
            # preludes. This build's own cgroup is outside every contained
            # slice, so a session reaches the stand-in systemd-run and a
            # helper reaches the line after the prelude.
            printf '%s\n' 'set -euo pipefail' > codex.sh
            cat >> codex.sh <<'PRELUDE'
            ${scopePreludes.codex}
            PRELUDE
            echo 'echo in-place' >> codex.sh
            printf '%s\n' 'set -euo pipefail' > other.sh
            cat >> other.sh <<'PRELUDE'
            ${scopePreludes.other}
            PRELUDE
            echo 'echo in-place' >> other.sh

            launch() {
              wrapper="$1"
              want="$2"
              shift 2
              actual="$(${pkgs.bash}/bin/bash "$wrapper" "$@")"
              if [ "$actual" != "$want" ]; then
                echo "agent scope prelude: expected $want for $wrapper $*, got $actual" >&2
                exit 1
              fi
            }
            launch codex.sh scoped
            launch codex.sh scoped exec "fix the build"
            launch codex.sh scoped app-server
            launch codex.sh scoped app-server --listen stdio://
            launch codex.sh scoped proxy app-server
            launch codex.sh in-place app-server proxy --sock /run/fixture.sock
            launch codex.sh in-place app-server proxy
            launch codex.sh in-place --version
            launch codex.sh in-place --help
            # Another backend's wrapper has no such helper.
            launch other.sh scoped app-server proxy
            launch other.sh in-place --version

            touch "$out"
          '';
      scopePreludes =
        let
          backends = import ../../modules/features/dev/agents/backends.nix {
            inherit lib runtimeDefaults;
            pkgs = pkgs // {
              systemd = pkgs.writeShellScriptBin "systemd-run" ''
                echo scoped
              '';
            };
            scriptPkgs = { };
            agentRuntimePath = "";
            hermesRuntimePath = "";
            sinnixCfg = { };
            user = "fixture";
          };
        in
        {
          codex = backends.mkAgentScopePrelude { helperInvocations = backends.codexHelperInvocations; };
          other = backends.agentScopePrelude;
        };
      # The launch route on this repository's own descriptor: the queued
      # command is the descriptor's exec inside its environment, in its pool,
      # under its label, with its timeout.
      fixturePython = pkgs.python3;
      agentctlOperationLaunchFixture =
        pkgs.runCommand "agentctl-operation-launch-fixture"
          {
            nativeBuildInputs = [ fixturePython ];
          }
          ''
            # agentctl imports sinnix_lib for its atomic publication helpers,
            # so a hand-built path needs both packages, not just agentctl.
            export PYTHONPATH="${sinnixScriptRegistry.packageSet.agentctl}/${pkgs.python3.sitePackages}:${sinnixScriptRegistry.packageSet.sinnix-lib}/${pkgs.python3.sitePackages}"
            ${fixturePython}/bin/python - <<'PY'
            import json
            from pathlib import Path
            from tempfile import TemporaryDirectory

            from agentctl import launch, pueue
            from agentctl.config import Config
            from agentctl.projects import ProjectCatalog

            root = Path("${inputs.self}")
            project = ProjectCatalog([root]).get("sinnix")
            operation = project.operation("backup_snapshot")
            assert operation.timeout_seconds == 1800

            added = []

            def add(*, group, label, command, working_directory, after=(), stashed=False, priority=0):
                added.append({"group": group, "label": label, "command": command, "priority": priority})
                return 7

            pueue.add = add
            pueue.task = lambda task_id: None
            with TemporaryDirectory() as state:
                config = Config(
                    project_roots=(root,),
                    event_spool=Path(state) / "events.jsonl",
                    state_dir=Path(state),
                    agentctl_executable="agentctl",
                )
                started = launch.start_operation(config, project, operation)
                written = json.loads(Path(added[0]["command"][1]).read_text())
            assert started["task_id"] == 7
            assert added[0]["group"] == "bulk"
            assert added[0]["label"] == "sinnix:backup_snapshot"
            assert added[0]["priority"] == 0
            assert added[0]["command"][0] == "agentctl-run"
            assert tuple(written["argv"]) == project.environment.command_for(operation.command)
            assert written["timeout_seconds"] == 1800
            assert written["result_kind"] == "exit"
            PY
            touch "$out"
          '';
      agentctlRuntimeFixture = pkgs.runCommand "agentctl-runtime-tools-fixture" { } ''
        ${pkgs.python3}/bin/python - <<'PY'
        import json
        import os
        import subprocess
        import time
        from pathlib import Path

        root = Path(os.environ["TMPDIR"])
        home = root / "home"
        home.mkdir()
        config = root / "agentctl.json"
        config.write_text(json.dumps({"state_dir": str(root / "agentctl")}))
        environment = {
            "HOME": str(home),
            "PATH": "",
            "AGENTCTL_CONFIG": str(config),
        }
        with (root / "pueued.log").open("w+") as log:
            daemon = subprocess.Popen(
                ["${pkgs.pueue}/bin/pueued"],
                env=environment, stdout=log, stderr=log,
            )
            try:
                deadline = time.monotonic() + 10
                while True:
                    result = subprocess.run(
                        ["${sinnixScriptRegistry.packageSet.agentctl}/bin/agentctl", "job", "list", "--json"],
                        env=environment, capture_output=True, text=True, timeout=5,
                    )
                    if result.returncode == 0:
                        assert json.loads(result.stdout) == []
                        break
                    assert "not installed" not in result.stderr, result.stderr
                    if daemon.poll() is not None or time.monotonic() >= deadline:
                        log.seek(0)
                        raise AssertionError(result.stderr + log.read())
                    time.sleep(0.05)
            finally:
                daemon.terminate()
                try:
                    daemon.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait()
        PY
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
            cp ${../../dots/_ai/skills/desktop-control/scripts/kitty-remote-control.sh} "$helper"
            chmod +x "$helper"
            patchShebangs "$helper"
            ${pkgs.bash}/bin/bash ${../../flake/tests/kitty-agent-here.sh} "$helper"
            touch "$out"
          '';
      kittyLaunchKeepFocusFixture =
        pkgs.runCommand "kitty-launch-keep-focus-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.gnused
              pkgs.jq
            ];
          }
          ''
            helper="$TMPDIR/kitty-remote-control.sh"
            cp ${../../dots/_ai/skills/desktop-control/scripts/kitty-remote-control.sh} "$helper"
            chmod +x "$helper"
            patchShebangs "$helper"
            ${pkgs.bash}/bin/bash ${../../flake/tests/kitty-launch-keep-focus.sh} "$helper"
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
            hook="$TMPDIR/pretooluse-bash.py"
            cp ${../../dots/claude/hooks/pretooluse-bash.py} "$hook"
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
              sinnixScriptRegistry.packageSet.beads
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${../../flake/tests/bd-dolt-authority.sh} ${sinnixScriptRegistry.packageSet.beads}/bin/bd
            touch "$out"
          '';
      chatgptConversationsFixture =
        pkgs.runCommand "chatgpt-conversations-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.curl
              pkgs.findutils
              pkgs.fd
              pkgs.gnugrep
              pkgs.gnused
              pkgs.jq
              pkgs.nodejs
            ];
          }
          ''
            skill="$TMPDIR/chatgpt-conversations"
            mkdir -p "$skill/scripts"
            cp ${../../dots/_ai/skills/chatgpt-conversations/scripts/sinnix-chatgpt-conversations} "$skill/scripts/sinnix-chatgpt-conversations"
            cp ${../../dots/_ai/skills/chatgpt-conversations/scripts/download-native.mjs} "$skill/scripts/download-native.mjs"
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
            toggle="$TMPDIR/toggle-scratch"
            cp ${../../scripts/hyprland-ocr} "$ocr"
            cp ${../../scripts/toggle-scratch} "$toggle"
            chmod +x "$ocr" "$toggle"
            patchShebangs "$ocr" "$toggle"
            ${pkgs.bash}/bin/bash ${../../flake/tests/desktop-capture.sh} "$ocr" "$toggle"
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
      # The rank-options skill is instructions over scripts/sinnix-rank, so its
      # suite drives the real CLI in a repository-shaped fixture root. Native
      # clients discover every SKILL.md beneath the live root, so the fixture
      # checks that source directly rather than a generated farm.
      #
      # Provably fails when: `record` stores the loser, `settled` stops
      # following the stopping threshold in either direction, a re-`add`
      # re-appends registered items, `add` stops refusing a duplicate label or
      # a changed option under a live id, the evidence block stops reporting
      # disconnected components, private option text reaches the working tree
      # or the diff, or root discovery stops finding the skill. Each verified
      # by mutation.
      rankOptionsSkillFixture =
        pkgs.runCommand "rank-options-skill-fixture"
          {
            nativeBuildInputs = [
              (pkgs.python3.withPackages (ps: [
                ps.pytest
                sinnixScriptRegistry.packageSet.sinnix-lib
              ]))
              pkgs.coreutils
            ];
          }
          ''
            test -e ${../../dots/_ai/skills/rank-options/SKILL.md}

            root="$TMPDIR/repo"
            mkdir -p "$root/scripts" "$root/pkgs" "$root/flake/data" "$root/dots/_ai/skills"
            install -m 0755 ${../../scripts/sinnix-rank} "$root/scripts/sinnix-rank"
            patchShebangs "$root/scripts/sinnix-rank"
            cp -r ${../../pkgs/sinnix-rank-core} "$root/pkgs/sinnix-rank-core"
            cp -r ${../../dots/_ai/skills/rank-options} "$root/dots/_ai/skills/rank-options"
            chmod -R u+w "$root"
            cd "$root"
            HOME="$TMPDIR/home" SINNIX_REPO_ROOT="$root" \
              python3 -m pytest -q dots/_ai/skills/rank-options/tests
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
              # The attention hook is exercised under a pseudo-terminal.
              pkgs.util-linux
            ];
          }
          ''
            hooks="$TMPDIR/hooks"
            settings="$TMPDIR/settings.json"
            mkdir -p "$hooks"
            cp ${../../dots/claude/hooks}/*.sh ${../../dots/claude/hooks}/*.py "$hooks/"
            cp ${../../dots/claude/managed-settings.json} "$settings"
            chmod +x "$hooks"/*.sh "$hooks"/*.py
            patchShebangs "$hooks"
            ${pkgs.bash}/bin/bash ${../../flake/tests/hooks-harness.sh} "$hooks" "$settings" \
              ${agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexHooksSource}
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
    in
    {
      checks = {
        sinex-mcp-binding = sinexMcpBinding;
        agent-resource-policy = agentResourcePolicy;
        agent-npm-bootstrap-recovery = agentNpmBootstrapRecovery;
        agent-scope-guard = agentScopeGuardFixture;
        direnv-direct-commands = direnvDirectCommandsFixture;
        agentctl-operation-launch = agentctlOperationLaunchFixture;
        agentctl-runtime-tools = agentctlRuntimeFixture;
        preflight = preflightFixture;
        kitty-agent-here = kittyAgentHereFixture;
        kitty-launch-keep-focus = kittyLaunchKeepFocusFixture;
        bd-safety-hook = bdSafetyHookFixture;
        bd-dolt-authority = bdDoltAuthorityFixture;
        chatgpt-conversations = chatgptConversationsFixture;
        desktop-capture = desktopCaptureFixture;
        recovery-skills = recoverySkillsFixture;
        rank-options-skill = rankOptionsSkillFixture;
        hooks-harness = hooksHarnessFixture;
        agent-definitions = agentDefinitionsFixture;
      };

      checks = {
        dev-agent-tools-runtime = devAgentToolsRuntime;
      };
    };
}
