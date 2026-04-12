# Config Assertion Tests
#
# Fast tests that verify NixOS configurations evaluate correctly.
# No VM boot - just checks that options are set as expected.
#
# Run all: nix flake check
# Run one: nix build .#checks.x86_64-linux.nixos-dev-shell
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  pkgsFor = system: inputs.nixpkgs.legacyPackages.${system};
  coverage = import ./test-coverage.nix;
  checkTiers = import ./check-tiers.nix { inherit lib; };

  mkSpecChecks =
    system:
    let
      # Import test infrastructure only when checks are requested.
      testLib = import ./test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        mountTmpfsRoots
        baseTestConfig
        evalTestSpec
        expect
        mkFeatureTest
        mkServiceTest
        mkBundleTest
        mkSystemChecks
        ;
      hasCoverageLayer = layer: entry: builtins.elem layer (entry.layers or [ ]);
      smokeName = subject: "smoke-" + lib.replaceStrings [ "." ] [ "-" ] subject;
      semanticFeatureSubjects = [
        "cli.polylogue"
        "desktop.audio"
        "desktop.browser"
        "desktop.common-apps"
        "desktop.gaming"
        "desktop.hyprland"
        "desktop.mime"
        "desktop.terminal"
        "dev.agentTools"
        "dev.editors"
        "dev.git"
        "dev.mcp-servers"
        "dev.shell"
      ];
      semanticServiceSubjects = [
        "below"
        "polylogue"
        "power-watchdog"
        "sentinel"
        "terminal-capture"
        "transmission"
      ];
      semanticBundleSubjects = [
        "desktop"
        "dev"
      ];
      desktopSmokeBaseline = {
        sinnix.machine.isDesktop = true;
        sinnix.features.desktop.ui.enable = lib.mkDefault true;
      };
      mkFeatureSmokeSpec =
        subject:
        mkFeatureTest {
          name = smokeName subject;
          feature = "sinnix.features.${subject}.enable";
          extraModules = lib.optionals (lib.hasPrefix "desktop." subject) [
            ({ ... }: desktopSmokeBaseline)
          ];
          assertions = _config: [ ];
        };
      mkServiceSmokeSpec =
        subject:
        mkServiceTest {
          name = smokeName subject;
          service = subject;
          assertions = _config: [ ];
        };
      mkBundleSmokeSpec =
        subject:
        mkBundleTest {
          name = smokeName subject;
          bundle = subject;
          assertions = _config: [ ];
        };
      coverageFeatureSmokeSpecs = map mkFeatureSmokeSpec (
        builtins.filter (
          subject:
          hasCoverageLayer "eval" coverage.features.${subject}
          && !(builtins.elem subject semanticFeatureSubjects)
        ) (builtins.attrNames coverage.features)
      );
      coverageServiceSmokeSpecs = map mkServiceSmokeSpec (
        builtins.filter (
          subject:
          hasCoverageLayer "eval" coverage.services.${subject}
          && !(builtins.elem subject semanticServiceSubjects)
        ) (builtins.attrNames coverage.services)
      );
      coverageBundleSmokeSpecs = map mkBundleSmokeSpec (
        builtins.filter (
          subject:
          hasCoverageLayer "eval" coverage.bundles.${subject}
          && !(builtins.elem subject semanticBundleSubjects)
        ) (builtins.attrNames coverage.bundles)
      );

      # Helper to get HM config for assertions
      hmFor = config: config.home-manager.users.${config.sinnix.user.name};

      manualTestSpecs = [
        # === Feature Tests (using DSL) ===
        (mkFeatureTest {
          name = "dev-agent-tools";
          feature = "sinnix.features.dev.agentTools.enable";
          extraModules = [
            (
              { ... }:
              {
                sinnix.features.dev.shell.enable = true;
                sinnix.features.dev.mcp-servers.enable = true;
              }
            )
          ];
          assertions =
            config:
            let
              hm = hmFor config;
              managedEntryText =
                entry:
                if entry ? text && entry.text != null then
                  entry.text
                else if entry ? source && entry.source != null then
                  builtins.readFile entry.source
                else
                  "";
              managedEntrySource =
                entry: if entry ? source && entry.source != null then toString entry.source else "";
              findSelfReferentialLinks =
                dir:
                let
                  entries = builtins.readDir dir;
                  names = builtins.attrNames entries;
                  basename = baseNameOf (toString dir);
                  directHits = lib.optional (
                    entries ? ${basename} && entries.${basename} == "symlink"
                  ) "${toString dir}/${basename}";
                  nestedHits = lib.concatLists (
                    map (
                      name:
                      if entries.${name} == "directory" then
                        findSelfReferentialLinks (dir + "/${name}")
                      else
                        [ ]
                    ) names
                  );
                in
                directHits ++ nestedHits;
              forgeConfigText = builtins.readFile ../dots/forge/.forge.toml;
              forgeMcpConfig = builtins.fromJSON (managedEntryText hm.home.file."forge/.mcp.json");
              sharedSkillSelfLinks = findSelfReferentialLinks ../dots/_ai/skills;
            in
            [
              {
                assertion = builtins.match ".*\\$\\*.*" (hm.home.file.".local/bin/claude-team".text or "") == null;
                message = "Claude team wrapper must not flatten arguments via $*";
              }
              {
                assertion = sharedSkillSelfLinks == [ ];
                message = "Shared skills tree must not contain self-referential symlinks: ${lib.concatStringsSep ", " sharedSkillSelfLinks}";
              }
              (expect.hmFileExists hm ".local/bin/claude" "Claude wrapper must exist")
              (expect.hmFileExists hm ".local/bin/codex" "Codex wrapper must exist")
              (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*render-agents.*"
                "Codex wrapper must not render AGENTS on every launch"
              )
              (expect.hmPackagedWrapper hm ".local/bin/forge" {
                envVar = "FORGE_BIN";
                binaryFragments = [ "/bin/forge" ];
                forbidRegexes = [ "curl -fsSL" ];
              } "Forge wrapper must launch the packaged binary directly")
              (expect.hmFileExists hm ".local/bin/forge" "Forge wrapper must exist")
              (expect.activationExists hm "renderGlobalForgeAgents"
                "Global Forge AGENTS render activation must exist"
              )
              (expect.hmFileExists hm "forge/skills" "Forge skill root must be linked from the shared skill tree")
              {
                assertion = !(hm.home.file."forge/skills".recursive or false);
                message = "Forge skill root must stay a direct directory symlink, not a recursive materialization";
              }
              (expect.textContains hm.programs.zsh.initContent "export FORGE_BIN=\"$HOME/.local/bin/forge\""
                "Zsh init must source Forge via the managed wrapper path"
              )
              (expect.hmFileExists hm "forge/.forge.toml"
                "Forge config must be managed under ~/forge/.forge.toml"
              )
              (expect.textContainsAll forgeConfigText [
                "provider_id = \"codex\""
                "model_id = \"gpt-5.4\""
                "auto_dump = \"json\""
                "auto_open_dump = false"
              ] "Forge config must preserve the Codex session defaults and dump settings")
              (expect.textContainsAll forgeConfigText [
                "debug_requests = \""
                "/forge/logs/requests\""
                "max_conversations = 1000000"
                "auto_update = false"
                "frequency = \"weekly\""
              ] "Forge config must keep durable request logs and disable self-updates")
              (expect.textContainsAll forgeConfigText [
                "max_fetch_chars = 75000"
                "max_file_read_batch_size = 64"
                "max_parallel_file_reads = 64"
                "max_read_lines = 4000"
                "max_requests_per_turn = 100"
                "max_tool_failure_per_turn = 5"
                "tool_timeout_secs = 600"
              ] "Forge config must keep the bounded runtime guardrails")
              (expect.textNotMatches forgeConfigText ".*custom_history_path.*"
                "Forge config must rely on Forge's native history storage path"
              )
              (expect.textNotMatches forgeConfigText ".*[[]compact[]].*"
                "Forge config must not override upstream compaction defaults"
              )
              (expect.persistedHomeDir config "forge" "Forge home directory must be persisted under ~/forge")
              (expect.persistedHomeDir config ".config/claude"
                "Claude config directory must be persisted under ~/.config/claude"
              )
              (expect.persistedHomeDir config ".codex" "Codex home directory must be persisted under ~/.codex")
              (expect.persistedHomeDir config ".gemini" "Gemini home directory must be persisted under ~/.gemini")
              (expect.hmFileExists hm ".local/bin/gemini" "Gemini wrapper must exist")
              (expect.hmFileTextNotMatches hm ".local/bin/gemini" ".*render-agents.*"
                "Gemini wrapper must not render instructions on every launch"
              )
              (expect.hmPackagedWrapper hm ".local/bin/gemini" {
                envVar = "GEMINI_BIN";
                binaryFragments = [ "/bin/gemini" ];
                forbidRegexes = [
                  "npx"
                  "bundle/index\\.js"
                ];
              } "Gemini wrapper must launch the packaged binary directly")
              (expect.xdgConfigFileExists hm "claude/CLAUDE.md" "Claude instruction root must exist")
              (expect.xdgConfigFileExists hm "claude/skills" "Claude skills symlink must exist")
              {
                assertion = !(hm.xdg.configFile."claude/skills".recursive or false);
                message = "Claude skills must stay a direct directory symlink, not a recursive materialization";
              }
              (expect.xdgConfigFileExists hm "claude/world-model" "Claude world model tree must exist")
              (expect.xdgConfigFileExists hm "claude/operational" "Claude operational knowledge tree must exist")
              (expect.activationExists hm "renderGlobalCodexAgents"
                "Global Codex AGENTS render activation must exist"
              )
              (expect.activationExists hm "renderGlobalGeminiAgents"
                "Global Gemini instruction render activation must exist"
              )
            ];
        })

        (mkFeatureTest {
          name = "dev-shell";
          feature = "sinnix.features.dev.shell.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              managedEntryText =
                entry:
                if entry ? text && entry.text != null then
                  entry.text
                else if entry ? source && entry.source != null then
                  builtins.readFile entry.source
                else
                  "";
              managedEntrySource =
                entry: if entry ? source && entry.source != null then toString entry.source else "";
            in
            [
              {
                assertion = hm.programs.zsh.enable;
                message = "Zsh must be enabled";
              }
              {
                assertion = hm.programs.starship.enable;
                message = "Starship must be enabled";
              }
              {
                assertion = hm.programs.atuin.enable;
                message = "Atuin must be enabled";
              }
              {
                assertion = hm.programs.fzf.enable;
                message = "FZF must be enabled";
              }
              {
                assertion = hm.programs.zoxide.enable;
                message = "Zoxide must be enabled";
              }
              (expect.sessionVariableMatches hm "LYNCHPIN_PYTHON" ".*/bin/lynchpin-python"
                "Dev shell must export the system-wide Lynchpin API interpreter path"
              )
              (expect.sessionVariableMatches hm "POLYLOGUE_PYTHON" ".*/bin/polylogue-python"
                "Dev shell must export the system-wide Polylogue API interpreter path"
              )
              {
                assertion = hm.programs.zsh.shellAliases.ccusage == "ccusage";
                message = "ccusage alias must resolve to the packaged CLI";
              }
              {
                assertion = builtins.any (name: lib.hasPrefix "lynchpin-python" name) (
                  map (pkg: pkg.name or "") hm.home.packages
                );
                message = "Dev shell must install the Lynchpin API interpreter wrapper";
              }
              {
                assertion = builtins.any (name: lib.hasPrefix "polylogue-python" name) (
                  map (pkg: pkg.name or "") hm.home.packages
                );
                message = "Dev shell must install the Polylogue API interpreter wrapper";
              }
              {
                assertion = lib.hasInfix "unsetopt prompt_sp" hm.programs.zsh.initContent;
                message = "Zsh init must disable PROMPT_SP to avoid stray partial-line prompt markers";
              }
            ];
        })

        (mkFeatureTest {
          name = "dev-git";
          feature = "sinnix.features.dev.git.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              gitSettings = hm.programs.git.settings;
              ignoreGlobal = hm.home.file.".config/git/ignore_global".text or "";
              githubHelper = gitSettings."credential \"https://github.com\"".helper or "";
            in
            [
              (expect.hmFileExists hm ".config/git/ignore_global"
                "Git feature must manage the global ignore file"
              )
              (expect.textContains ignoreGlobal "AGENTS.md"
                "Git global ignore must suppress generated AGENTS files by default"
              )
              (expect.mkAssertion (
                (gitSettings.init.defaultBranch or null) == "master"
              ) "Git must retain the canonical default branch name")
              (expect.mkAssertion (
                (gitSettings.merge.conflictStyle or null) == "zdiff3"
              ) "Git must use zdiff3 conflict markers")
              (expect.mkAssertion ((gitSettings.pull.rebase or false) == true) "Git pulls must default to rebase")
              (expect.mkAssertion (
                (gitSettings.rerere.enabled or false) == true
              ) "Git must enable rerere for repeated conflict reuse")
              (expect.textContains githubHelper "/run/agenix/github-token"
                "GitHub credential helper must read from the managed agenix token path"
              )
              (expect.mkAssertion (hm.programs.delta.enableGitIntegration or false
              ) "Delta must stay wired through git integration")
            ];
        })

        (mkFeatureTest {
          name = "dev-mcp-servers";
          feature = "sinnix.features.dev.mcp-servers.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              managedEntryText =
                entry:
                if entry ? text && entry.text != null then
                  entry.text
                else if entry ? source && entry.source != null then
                  builtins.readFile entry.source
                else
                  "";
              managedEntrySource =
                entry: if entry ? source && entry.source != null then toString entry.source else "";
              codexConfigText = builtins.readFile ../dots/codex/config.toml;
              claudeSettings = builtins.fromJSON (builtins.readFile ../dots/claude/settings.json);
              geminiSettings = builtins.fromJSON (builtins.readFile ../dots/gemini/settings.json);
              forgeMcpConfig = builtins.fromJSON (managedEntryText hm.home.file."forge/.mcp.json");
            in
            [
              {
                assertion =
                  builtins.match ".*zsh -lc.*" (
                    builtins.readFile ../dots/_ai/skills/agent-orchestration/scripts/launch_agent_tabs.sh
                  ) == null;
                message = "Agent launcher must not wrap kitty launches in zsh -lc";
              }
              (expect.hmFileExists hm ".codex/config.toml" "Codex config must be managed")
              (expect.hmFileExists hm ".codex/skills"
                "Codex skills must be linked from the dedicated dots/codex/skills tree"
              )
              {
                assertion = !(hm.home.file.".codex/skills".recursive or false);
                message = "Codex skills must stay a direct directory symlink, not a recursive materialization";
              }
              (expect.textContains (managedEntrySource
                hm.home.file.".local/bin/mcp-firecrawl"
              ) "/bin/mcp-firecrawl" "Firecrawl wrapper must point at the packaged binary")
              (expect.textContains (managedEntrySource
                hm.home.file.".local/bin/mcp-playwright"
              ) "/bin/mcp-playwright" "Playwright wrapper must point at the packaged binary")
              (expect.textContains (managedEntryText
                hm.home.file.".local/bin/mcp-playwright"
              ) "/bin/mcp-server-playwright" "Playwright wrapper must launch the packaged server entrypoint")
              (expect.textContains (managedEntrySource
                hm.home.file.".local/bin/mcp-polylogue"
              ) "/bin/mcp-polylogue" "Polylogue wrapper must point at the packaged binary")
              (expect.textContains codexConfigText "[mcp_servers.polylogue]"
                "Codex config must declare the Polylogue MCP server"
              )
              (expect.textContains codexConfigText "command = \"mcp-polylogue\""
                "Codex config must call the packaged Polylogue MCP wrapper"
              )
              (expect.textContains codexConfigText "[mcp_servers.context7]"
                "Codex config must declare the Context7 MCP server"
              )
              (expect.textContains codexConfigText "url = \"https://mcp.context7.com/mcp\""
                "Codex config must point Context7 at the remote hosted endpoint"
              )
              (expect.textContains codexConfigText "bearer_token_env_var = \"CONTEXT7_API_KEY\""
                "Codex config must use bearer token auth for Context7"
              )
              (expect.textContains codexConfigText "[mcp_servers.github]"
                "Codex config must declare the GitHub MCP server"
              )
              (expect.textContains codexConfigText "bearer_token_env_var = \"GITHUB_TOKEN\""
                "Codex config must keep GitHub token lookup in the environment"
              )
              (expect.attrPathEq claudeSettings [
                "mcpServers"
                "polylogue"
                "command"
              ] "mcp-polylogue" "Claude config must call the packaged Polylogue MCP wrapper")
              (expect.attrPathEq geminiSettings [
                "mcpServers"
                "polylogue"
                "command"
              ] "mcp-polylogue" "Gemini config must call the packaged Polylogue MCP wrapper")
              {
                assertion = !(hm.home.file.".gemini/skills".recursive or false);
                message = "Gemini skills must stay a direct directory symlink, not a recursive materialization";
              }
              (expect.attrPathEq geminiSettings [
                "mcpServers"
                "context7"
                "httpUrl"
              ] "https://mcp.context7.com/mcp" "Gemini config must point Context7 at the remote hosted endpoint")
              (expect.attrPathEq geminiSettings [
                "mcpServers"
                "github"
                "httpUrl"
              ] "https://api.githubcopilot.com/mcp/" "Gemini config must keep the GitHub MCP endpoint")
              (expect.attrPathEq geminiSettings [
                "mcpServers"
                "github"
                "headers"
                "Authorization"
              ] "Bearer \${GITHUB_TOKEN}" "Gemini config must keep GitHub auth as runtime header expansion")
              (expect.attrPathEq geminiSettings [
                "general"
                "enableAutoUpdate"
              ] false "Gemini must keep self-update disabled")
              (expect.attrPathEq geminiSettings [
                "general"
                "enableAutoUpdateNotification"
              ] false "Gemini must keep update notifications disabled")
              (expect.attrPathEq geminiSettings [
                "general"
                "checkpointing"
                "enabled"
              ] true "Gemini must retain checkpointing")
              (expect.attrPathEq geminiSettings [
                "general"
                "sessionRetention"
                "maxCount"
              ] 1000000 "Gemini must keep the long session-retention budget")
              (expect.attrPathEq geminiSettings [
                "model"
                "maxSessionTurns"
              ] (-1) "Gemini must keep unlimited session turns")
              (expect.attrPathEq forgeMcpConfig [
                "mcpServers"
                "context7"
                "url"
              ] "https://mcp.context7.com/mcp" "Forge MCP config must point Context7 at the remote hosted endpoint")
              (expect.attrPathEq forgeMcpConfig [
                "mcpServers"
                "firecrawl"
                "command"
              ] "mcp-firecrawl" "Forge MCP config must call the packaged Firecrawl wrapper")
              (expect.attrPathEq forgeMcpConfig [
                "mcpServers"
                "playwright"
                "command"
              ] "mcp-playwright" "Forge MCP config must call the packaged Playwright wrapper")
              (expect.attrPathEq forgeMcpConfig [ "mcpServers" "playwright" "args" ] [ "--headless" ]
                "Forge MCP config must keep Playwright headless by default"
              )
              (expect.attrPathEq forgeMcpConfig [
                "mcpServers"
                "polylogue"
                "command"
              ] "mcp-polylogue" "Forge MCP config must call the packaged Polylogue wrapper")
            ];
        })

        {
          name = "services-polylogue";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "polylogue-test";
                sinnix.services.polylogue.enable = true;
              }
            )
          ];
          assertions =
            config:
            let
              hm = hmFor config;
              service = hm.systemd.user.services."polylogue-run".Service or { };
              timer = hm.systemd.user.timers."polylogue-run".Timer or { };
              execStart =
                let
                  raw = service.ExecStart or [ ];
                in
                if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
            in
            [
              (expect.hmUserServiceExists hm "polylogue-run" "Polylogue user service must exist")
              (expect.hmUserTimerExists hm "polylogue-run" "Polylogue user timer must exist")
              (expect.textContains execStart "/bin/polylogue --plain run"
                "Polylogue user service must run the packaged CLI directly"
              )
              (expect.attrPathEq service [
                "TimeoutStartSec"
              ] "10min" "Polylogue ingestion must keep the bounded 10 minute timeout")
              (expect.attrPathEq service [
                "MemoryHigh"
              ] "2G" "Polylogue ingestion must retain the memory high watermark")
              (expect.attrPathEq service [
                "MemoryMax"
              ] "4G" "Polylogue ingestion must retain the hard memory limit")
              (expect.attrPathEq timer [
                "Persistent"
              ] true "Polylogue timer must catch up missed runs after sleep")
            ];
        }

        (mkFeatureTest {
          name = "dev-editors-antigravity";
          feature = "sinnix.features.dev.editors.enable";
          extraModules = [
            (
              { ... }:
              {
                sinnix.features.dev.editors.antigravity.enable = true;
              }
            )
          ];
          assertions =
            config:
            let
              hasAntigravityDir =
                entry:
                if builtins.isAttrs entry then
                  (entry.directory or null) == ".config/Antigravity"
                else
                  entry == ".config/Antigravity";
            in
            [
              {
                assertion = builtins.any hasAntigravityDir config.sinnix.persistence.home.directories;
                message = "Antigravity state must be persisted under ~/.config/Antigravity";
              }
            ];
        })

        (mkFeatureTest {
          name = "cli-polylogue";
          feature = "sinnix.features.cli.polylogue.enable";
          assertions =
            config:
            let
              packageNames = map (pkg: pkg.name or "") (hmFor config).home.packages;
            in
            [
              {
                assertion =
                  builtins.any (name: lib.hasPrefix "polylogue" name) packageNames
                  && builtins.any (name: lib.hasPrefix "polylogue-python" name) packageNames;
                message = "Polylogue feature must install the packaged Polylogue CLI and API wrappers";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-mime";
          feature = "sinnix.features.desktop.mime.enable";
          assertions =
            config:
            let
              defaultApps = (hmFor config).xdg.mimeApps.defaultApplications;
            in
            [
              {
                assertion = defaultApps."x-scheme-handler/http" == [ "google-chrome.desktop" ];
                message = "HTTP links must default to Google Chrome";
              }
              {
                assertion = defaultApps."x-scheme-handler/https" == [ "google-chrome.desktop" ];
                message = "HTTPS links must default to Google Chrome";
              }
              {
                assertion = defaultApps."text/html" == [ "google-chrome.desktop" ];
                message = "HTML documents must default to Google Chrome";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-hyprland";
          feature = "sinnix.features.desktop.hyprland.enable";
          extraModules = [
            (
              { lib, ... }:
              {
                hardware.graphics.enable = lib.mkForce false;
              }
            )
          ];
          assertions = config: [
            {
              assertion = config.programs.hyprland.enable;
              message = "Hyprland must be enabled";
            }
            {
              assertion = config.programs.hyprland.withUWSM;
              message = "UWSM must be enabled";
            }
            {
              assertion = lib.hasInfix "exec uwsm start hyprland-uwsm.desktop" (
                (hmFor config).programs.zsh.loginExtra or ""
              );
              message = "TTY Hyprland login must stay unwrapped by default";
            }
          ];
        })

        (mkFeatureTest {
          name = "desktop-audio";
          feature = "sinnix.features.desktop.audio.enable";
          assertions =
            config:
            let
              wireplumber = config.services.pipewire.wireplumber.extraConfig;
              xm4Rules = wireplumber."12-preferred-xm4-output"."monitor.bluez.rules" or [ ];
              isXm4Rule =
                rule:
                (builtins.elemAt (rule.matches or [ ]) 0)."node.name" or null
                == "~bluez_output.*AC_80_0A_D4_08_48.*"
                && (rule.actions.update-props."priority.session" or null) == 2100
                && (rule.actions.update-props."priority.driver" or null) == 2100;
            in
            [
              {
                assertion = config.services.pipewire.enable or false;
                message = "Desktop audio must enable PipeWire";
              }
              {
                assertion = config.services.pipewire.wireplumber.enable or false;
                message = "Desktop audio must enable WirePlumber";
              }
              {
                assertion = builtins.any isXm4Rule xm4Rules;
                message = "WH-1000XM4 must be preferred as the default Bluetooth sink when it appears";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-common-apps";
          feature = "sinnix.features.desktop.common-apps.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              packageNames = map (pkg: pkg.name or "") hm.home.packages;
              yaziConfig = builtins.readFile ../dots/yazi/yazi.toml;
            in
            [
              {
                assertion = hm.xdg.configFile ? "yazi/yazi.toml";
                message = "Common desktop apps must link the Yazi config";
              }
              {
                assertion = hm.xdg.configFile ? "yazi/plugins/sinnix-video-preview.yazi/main.lua";
                message = "Common desktop apps must link the custom Yazi video preview plugin";
              }
              {
                assertion = builtins.any (name: lib.hasPrefix "media-preview-cache" name) packageNames;
                message = "Common desktop apps must install the media preview cache helper";
              }
              {
                assertion =
                  lib.hasInfix "image_delay = 0" yaziConfig
                  && lib.hasInfix "run = \"sinnix-video-preview\"" yaziConfig;
                message = "Yazi must use the custom instant video preview configuration";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-terminal";
          feature = "sinnix.features.desktop.terminal.enable";
          assertions =
            config:
            let
              hm = hmFor config;
            in
            [
              {
                assertion = hm.programs.kitty.enable;
                message = "Kitty must be enabled";
              }
              {
                assertion =
                  hm.programs.kitty.settings.shell == "${hm.home.homeDirectory}/.local/bin/sinnix-captured-shell";
                message = "Kitty must launch through the capture wrapper";
              }
              {
                assertion = hm.programs.kitty.settings.open_url_with == "xdg-open";
                message = "Kitty URL opening must stay delegated to xdg-open";
              }
              {
                assertion = hm.programs.kitty.settings.allow_remote_control == "socket-only";
                message = "Kitty remote control must stay socket-only";
              }
              {
                assertion =
                  let
                    mode = hm.programs.kitty.shellIntegration.mode or "";
                  in
                  lib.hasInfix "no-prompt-mark" mode && lib.hasInfix "no-title" mode && lib.hasInfix "no-cursor" mode;
                message = "Kitty shell integration must disable prompt/title/cursor features that interfere with the custom zsh prompt";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-browser";
          feature = "sinnix.features.desktop.browser.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              quteConfig = builtins.readFile ../dots/qutebrowser/config.py;
              chromePkgs = builtins.filter (pkg: (pkg.pname or "") == "google-chrome") hm.home.packages;
              chromePkg = if chromePkgs == [ ] then null else builtins.head chromePkgs;
              chromeDesktop =
                if chromePkg == null then
                  ""
                else
                  builtins.readFile "${chromePkg}/share/applications/google-chrome.desktop";
            in
            [
              {
                assertion = hm.xdg.configFile ? "qutebrowser/config.py";
                message = "Qutebrowser config must be linked";
              }
              {
                assertion = builtins.match ".*configfiles\\.read_autoconfig.*" quteConfig == null;
                message = "Qutebrowser config must target the pinned modern API directly";
              }
              {
                assertion = builtins.match ".*except Exception:.*" quteConfig == null;
                message = "Qutebrowser config must not silently swallow broad exceptions";
              }
              {
                assertion =
                  chromePkg != null
                  && !(lib.hasPrefix "google-chrome-trigger-capture" (chromePkg.name or ""))
                  && builtins.match ".*Exec=.*/bin/google-chrome-stable.*" chromeDesktop != null;
                message = "Chrome desktop entry must point at the normal binary by default";
              }
            ];
        })

        (mkFeatureTest {
          name = "desktop-gaming";
          feature = "sinnix.features.desktop.gaming.enable";
          assertions =
            config:
            let
              hm = hmFor config;
              packageNames = map (pkg: pkg.name or "") hm.home.packages;
            in
            [
              {
                assertion = builtins.any (name: name == "factorio-steam") packageNames;
                message = "Gaming feature must install the factorio-steam launcher";
              }
              {
                assertion = config.sinnix.features.desktop.gaming.factorio.username == "Sinityy";
                message = "Gaming feature must preserve the nested Factorio username option";
              }
            ];
        })

        {
          name = "networking-resolved-router-authority";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "networking-test";
              }
            )
          ];
          assertions = config: [
            {
              assertion = config.networking.networkmanager.dns == "systemd-resolved";
              message = "NetworkManager must keep using systemd-resolved as the local stub";
            }
            {
              assertion = config.services.resolved.enable;
              message = "systemd-resolved must stay enabled";
            }
            {
              assertion = config.services.resolved.settings.Resolve.DNSSEC == false;
              message = "Local systemd-resolved DNSSEC must be disabled when the router is the DNS authority";
            }
            {
              assertion = config.services.resolved.settings.Resolve.FallbackDNS == "";
              message = "Local systemd-resolved fallback DNS must be disabled when the router is authoritative";
            }
          ];
        }

        {
          name = "nextcloud-storage-wiring";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "nextcloud-storage-test";
              }
            )
          ];
          assertions =
            config:
            let
              fixRclonePermissions = config.system.activationScripts.fixRclonePermissions.text or "";
            in
            [
              {
                assertion = config.age.secrets ? "nextcloud-address";
                message = "Agenix must define the nextcloud-address secret";
              }
              {
                assertion = config.age.secrets ? "borg-passphrase";
                message = "Agenix must define the borg-passphrase secret";
              }
              {
                assertion = config.age.secrets ? "nextcloud-webdav-credentials";
                message = "Agenix must still define the Nextcloud credentials secret";
              }
              {
                assertion = config.services.borgbackup.jobs.realm.encryption.mode == "repokey-blake2";
                message = "Realm Borg job must use repokey-blake2";
              }
              {
                assertion = config.services.borgbackup.jobs.persist.encryption.mode == "repokey-blake2";
                message = "Persist Borg job must use repokey-blake2";
              }
              {
                assertion = config.system.activationScripts ? fixRclonePermissions;
                message = "Rclone credential permissions must be repaired at activation time";
              }
              {
                assertion = lib.hasInfix ".config/rclone/rclone.conf" fixRclonePermissions;
                message = "Rclone permission repair must target the user's persisted rclone config";
              }
              {
                assertion = lib.hasInfix "chmod 600" fixRclonePermissions;
                message = "Rclone permission repair must lock the credentials file to mode 600";
              }
              {
                assertion = !(config.system.activationScripts ? nextcloudRcloneRuntime);
                message = "Legacy Nextcloud runtime mount-unit rendering must remain disabled until the boot-cycle issue is fixed";
              }
            ];
        }

        # === Service Tests (using DSL) ===
        (mkServiceTest {
          name = "services-below";
          service = "below";
          assertions = config: [
            {
              assertion = config.systemd.services ? below;
              message = "Below service must exist";
            }
            {
              assertion = config.environment.systemPackages != [ ];
              message = "Below package must be installed";
            }
          ];
        })

        (mkServiceTest {
          name = "services-power-watchdog";
          service = "power-watchdog";
          assertions = config: [
            {
              assertion = config.systemd.services ? power-watchdog;
              message = "power-watchdog service must exist";
            }
          ];
        })

        (mkServiceTest {
          name = "services-transmission";
          service = "transmission";
          assertions = config: [
            {
              assertion = config.services.transmission.enable;
              message = "Transmission must be enabled";
            }
            {
              assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
              message = "Transmission must declare required mounts";
            }
          ];
        })

        (mkServiceTest {
          name = "services-terminal-capture";
          service = "terminal-capture";
          assertions = config: [
            {
              assertion = builtins.any (
                rule: builtins.match ".*captures/asciinema.*" rule != null
              ) config.systemd.tmpfiles.rules;
              message = "Asciinema captures directory tmpfiles entry must exist";
            }
            {
              assertion = (hmFor config).home.file ? ".local/bin/sinnix-captured-shell";
              message = "The terminal capture launcher must be linked into ~/.local/bin";
            }
            {
              assertion =
                (hmFor config).home.sessionVariables.SINNIX_CAPTURE_ROOT == "/realm/data/captures/asciinema";
              message = "The capture root session variable must point at the canonical asciinema directory";
            }
            {
              assertion = (hmFor config).home.sessionVariables.SINNIX_CAPTURE_TERMINAL == "kitty";
              message = "The capture terminal session variable must identify Kitty";
            }
            {
              assertion = lib.hasInfix "sinnix-terminal-capture-hooks.zsh" (hmFor config)
              .programs.zsh.initContent;
              message = "The zsh init path must source the terminal capture hooks";
            }
            {
              assertion =
                builtins.match ".*SUCCESS_BACKOFF_SECONDS.*sleep.*" (builtins.readFile ../scripts/rawlog-loop)
                != null;
              message = "rawlog-loop must back off after fast success exits";
            }
          ];
        })

        (mkServiceTest {
          name = "services-sentinel";
          service = "sentinel";
          assertions = config: [
            {
              assertion = config.systemd.services ? sinnix-sentinel;
              message = "sinnix-sentinel oneshot service must exist";
            }
            {
              assertion = config.systemd.timers ? sinnix-sentinel;
              message = "sinnix-sentinel timer must exist";
            }
            {
              assertion = config.environment.etc ? "sinnix/health-policy.json";
              message = "health-policy.json must be generated (from introspection.nix)";
            }
            {
              assertion = config.environment.etc ? "sinnix/config.json";
              message = "config.json must be generated (from introspection.nix)";
            }
            {
              assertion = builtins.any (
                rule: builtins.match ".*sinnix-sentinel.*" rule != null
              ) config.systemd.tmpfiles.rules;
              message = "sentinel event log directory must be created via tmpfiles";
            }
          ];
        })

        # Note: sinex service test omitted — sinex requires PostgreSQL, TLS certs,
        # and agenix secrets which are too heavyweight for config-only assertion tests.
        # The sinex service is verified via the full sinnix-prime build.

        # === Bundle Tests (using DSL) ===
        (mkBundleTest {
          name = "bundle-dev";
          bundle = "dev";
          assertions =
            config:
            let
              hm = hmFor config;
            in
            [
              {
                assertion = hm.programs.zsh.enable;
                message = "Dev bundle must enable zsh";
              }
              {
                assertion = hm.programs.git.enable;
                message = "Dev bundle must enable git";
              }
              {
                assertion = hm.programs.tmux.enable;
                message = "Dev bundle must enable tmux";
              }
            ];
        })

        (mkBundleTest {
          name = "bundle-desktop";
          bundle = "desktop";
          extraModules = [
            (
              { lib, pkgs, ... }:
              {
                hardware.graphics.enable = lib.mkForce false;
                # Provide dummy graphics package for headless test evaluation
                hardware.graphics.package = lib.mkForce pkgs.mesa;
                hardware.graphics.package32 = lib.mkForce pkgs.pkgsi686Linux.mesa;
              }
            )
          ];
          assertions = config: [
            {
              assertion = config.programs.hyprland.enable or false;
              message = "Desktop must enable hyprland";
            }
            {
              assertion = config.services.pipewire.enable or false;
              message = "Desktop must enable audio";
            }
          ];
        })

        # === Manual Tests (need custom module logic) ===
        {
          name = "minimal-no-features";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "minimal";
                sinnix.bundles.dev.enable = false;
              }
            )
          ];
          assertions =
            config:
            let
              hm = hmFor config;
            in
            [
              {
                assertion = !(hm.programs.starship.enable or false);
                message = "Starship should not be enabled in minimal";
              }
              {
                assertion = !(config.services.transmission.enable or false);
                message = "Transmission should not be enabled in minimal";
              }
            ];
        }

        {
          name = "desktop-bluetooth-persistence";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "desktop-bluetooth-persistence";
                sinnix.machine.isDesktop = true;
                sinnix.persistence.enable = true;
              }
            )
          ];
          assertions =
            config:
            let
              isBluetoothDir =
                entry:
                if builtins.isAttrs entry then
                  (entry.directory or null) == "/var/lib/bluetooth"
                else
                  entry == "/var/lib/bluetooth";
            in
            [
              {
                assertion = config.hardware.bluetooth.enable or false;
                message = "Desktop hosts must enable Bluetooth support";
              }
              {
                assertion = builtins.any isBluetoothDir config.sinnix.persistence.system.directories;
                message = "Bluetooth state must be persisted under /var/lib/bluetooth";
              }
            ];
        }

        {
          name = "paths-configured";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "paths-test";
              }
            )
          ];
          assertions = config: [
            {
              assertion = config.sinnix.paths.realmRoot == "/realm";
              message = "realmRoot must be /realm";
            }
            {
              assertion = config.sinnix.paths.dataRoot == "/realm/data";
              message = "dataRoot must be /realm/data";
            }
            {
              assertion = config.sinnix.paths.capturesRoot == "/realm/data/captures";
              message = "capturesRoot must be correct";
            }
            {
              assertion = config.sinnix.user.name == "sinity";
              message = "Default user must be sinity";
            }
          ];
        }

        # === Password/Secrets Safety Tests ===
        {
          name = "password-secrets-wiring";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "password-test";
              }
            )
          ];
          assertions = config: [
            {
              assertion = config.users.mutableUsers == false;
              message = "mutableUsers must be false (declarative passwords)";
            }
            {
              assertion = config.users.users.${config.sinnix.user.name} ? hashedPasswordFile;
              message = "User must have hashedPasswordFile set (not inline hash)";
            }
            {
              assertion = config.users.users.root ? hashedPasswordFile;
              message = "Root must have hashedPasswordFile set (not inline hash)";
            }
            {
              assertion =
                config.users.users.${config.sinnix.user.name}.hashedPasswordFile
                == config.sinnix.secrets.paths."${config.sinnix.user.name}-password";
              message = "User password file must point to agenix secret path";
            }
            {
              assertion = config.users.users.root.hashedPasswordFile == config.sinnix.secrets.paths.root-password;
              message = "Root password file must point to agenix secret path";
            }
            {
              assertion = config.age.secrets ? "${config.sinnix.user.name}-password";
              message = "Agenix must have user password secret configured";
            }
            {
              assertion = config.age.secrets ? "root-password";
              message = "Agenix must have root password secret configured";
            }
          ];
        }

        # === Router Config Tests ===
        # Verify sinnix-gw OpenWrt config evaluates without errors
        # (no NixOS VM needed — just checks the Nix expressions)
        {
          name = "router-config-evaluates";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "router-test";
              }
            )
          ];
          assertions =
            _config:
            let
              routerCfg = import ../hosts/sinnix-gw/default.nix { inherit lib; };
              openwrtLib = import ../modules/lib/openwrt.nix { inherit lib; };
              uciScript = openwrtLib.mkUciScript routerCfg.uci;
              pkgScript = openwrtLib.mkOpkgScript routerCfg.packages;

              # Helper: check if string contains a substring
              contains = haystack: needle: builtins.match ".*${lib.escapeRegex needle}.*" haystack != null;
              # Helper: check if string matches regex (multiline via [\s\S])
              matchesRegex = haystack: regex: builtins.match regex haystack != null;
            in
            [
              # ── Basic metadata ──
              {
                assertion = routerCfg.hostname == "sinnix-gw";
                message = "Router hostname must be sinnix-gw";
              }
              {
                assertion = routerCfg.address == "192.168.1.1";
                message = "Router address must be 192.168.1.1";
              }
              {
                assertion = builtins.length routerCfg.packages > 0;
                message = "Router must have packages to install";
              }
              {
                assertion = builtins.stringLength uciScript > 100;
                message = "UCI script must generate non-trivial output";
              }
              {
                assertion = builtins.stringLength pkgScript > 10;
                message = "Package script must generate output";
              }
              {
                assertion = builtins.stringLength routerCfg.postCommands > 100;
                message = "Post-commands must be non-empty";
              }

              # ── Ash compatibility (no pipefail) ──
              {
                assertion = !(contains uciScript "pipefail");
                message = "UCI script must not contain pipefail (ash incompatible)";
              }
              {
                assertion = !(contains pkgScript "pipefail");
                message = "Package script must not contain pipefail (ash incompatible)";
              }

              # ── UCI script is a fragment (no embedded shebang) ──
              {
                assertion = !(contains uciScript "#!/bin/sh");
                message = "UCI script must not contain shebang (it's a fragment, not standalone)";
              }

              # ── Critical UCI sections exist ──
              {
                assertion = contains uciScript "network.lan=";
                message = "UCI script must configure LAN interface";
              }
              {
                assertion = contains uciScript "network.wan=";
                message = "UCI script must configure WAN interface";
              }
              {
                assertion = contains uciScript "wireless.radio0=";
                message = "UCI script must configure radio0 (2.4GHz)";
              }
              {
                assertion = contains uciScript "wireless.radio1=";
                message = "UCI script must configure radio1 (5GHz)";
              }
              {
                assertion = contains uciScript "sqm.wan_qos=";
                message = "UCI script must configure SQM";
              }
              {
                assertion = contains uciScript "firewall.defaults=";
                message = "UCI script must configure firewall defaults";
              }
              {
                assertion = contains uciScript "dhcp.dnsmasq=";
                message = "UCI script must configure dnsmasq";
              }

              # ── UCI commit commands present ──
              {
                assertion = contains uciScript "uci commit network";
                message = "UCI script must commit network package";
              }
              {
                assertion = contains uciScript "uci commit wireless";
                message = "UCI script must commit wireless package";
              }
              {
                assertion = contains uciScript "uci commit firewall";
                message = "UCI script must commit firewall package";
              }

              # ── postCommands content ──
              {
                assertion = contains routerCfg.postCommands "authorized_keys";
                message = "Post-commands must deploy SSH authorized key";
              }
              {
                assertion = contains routerCfg.postCommands "https-dns-proxy";
                message = "Post-commands must configure https-dns-proxy (DoH)";
              }
              {
                assertion = contains routerCfg.postCommands "network reload";
                message = "Post-commands must reload network";
              }
              {
                assertion = contains routerCfg.postCommands "nf_conntrack_max";
                message = "Post-commands must tune conntrack table";
              }
            ];
        }

        # === Backup Tests ===
        {
          name = "backup-btrbk";
          modules = [
            mountTmpfsRoots
            baseTestConfig
            (
              { ... }:
              {
                networking.hostName = "backup-test";
              }
            )
          ];
          assertions =
            config:
            let
              hasConf = config.environment.etc ? "btrbk/btrbk.conf";
              conf = if hasConf then config.environment.etc."btrbk/btrbk.conf".text else "";
              realmJob = config.services.borgbackup.jobs.realm;
              persistJob = config.services.borgbackup.jobs.persist;
              subvolumeGuard = config.systemd.services.sinnix-realm-sinex-target-subvolume.script or "";
              hasTmpfilesRule =
                pattern:
                builtins.any (rule: builtins.match ".*${pattern}.*" rule != null) config.systemd.tmpfiles.rules;
            in
            [
              # Core service
              {
                assertion = config.systemd.services ? btrbk;
                message = "btrbk service must exist";
              }
              {
                assertion = config.systemd.timers ? btrbk;
                message = "btrbk timer must exist";
              }
              {
                assertion = builtins.match ".*btrfs subvolume show.*" subvolumeGuard != null;
                message = "sinex target guard must detect an existing Btrfs subvolume rather than requiring a mountpoint";
              }
              # Config deployed
              {
                assertion = hasConf;
                message = "btrbk config must be deployed to /etc";
              }
              # Config contains correct paths (guarded — conf is "" if etc file missing)
              {
                assertion = hasConf && builtins.match ".*volume /realm.*" conf != null;
                message = "btrbk config must include /realm volume";
              }
              # Retention policy present
              {
                assertion = hasConf && builtins.match ".*snapshot_preserve_min   latest.*" conf != null;
                message = "btrbk config must disable the default preserve-all snapshot minimum";
              }
              {
                assertion =
                  hasConf
                  &&
                    builtins.match ".*volume /realm\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +6h\n +snapshot_preserve +24h.*" conf
                    != null;
                message = "btrbk config must keep recent /realm snapshots in the .btrfs/snapshot layout";
              }
              {
                assertion =
                  hasConf
                  &&
                    builtins.match ".*volume /persist\n +snapshot_dir +\\.btrfs/snapshot\n +subvolume \\.\n +snapshot_preserve_min +6h\n +snapshot_preserve +24h.*" conf
                    != null;
                message = "btrbk config must keep recent /persist snapshots in the .btrfs/snapshot layout";
              }
              {
                assertion = realmJob.repo == "file:///outer-realm/backup/borg-realm-v2";
                message = "Realm Borg job must target the v2 encrypted repository via file URI";
              }
              {
                assertion = persistJob.repo == "file:///outer-realm/backup/borg-persist-v1";
                message = "Persist Borg job must target the encrypted persist repository via file URI";
              }
              {
                assertion = realmJob.paths == [ "/run/borgbackup-snapshot-inputs/realm/./" ];
                message = "Realm Borg job must archive the bind-mounted snapshot contents";
              }
              {
                assertion = persistJob.paths == [ "/run/borgbackup-snapshot-inputs/persist/./" ];
                message = "Persist Borg job must archive the bind-mounted snapshot contents";
              }
              {
                assertion = builtins.match ".*mount --bind.*" realmJob.preHook != null;
                message = "Realm Borg job must bind-mount the latest snapshot before backup";
              }
              {
                assertion = builtins.match ".*mount --bind.*" persistJob.preHook != null;
                message = "Persist Borg job must bind-mount the latest snapshot before backup";
              }
              # Snapshot dirs created by tmpfiles
              {
                assertion = builtins.any (
                  rule: builtins.match ".*\\.btrfs/snapshot.*" rule != null
                ) config.systemd.tmpfiles.rules;
                message = "Snapshot directories must be created via tmpfiles";
              }
              {
                assertion = hasTmpfilesRule "/run/borgbackup-snapshot-inputs";
                message = "Borg snapshot bind-mount staging directories must be created via tmpfiles";
              }
              {
                assertion = config.system.activationScripts ? borgRepositoryDirectories;
                message = "Borg repository directories must be created during activation";
              }
            ];
        }

      ];
      specByName = lib.listToAttrs (
        map
          (spec: {
            name = spec.name;
            value = spec;
          })
          (
            manualTestSpecs
            ++ coverageFeatureSmokeSpecs
            ++ coverageServiceSmokeSpecs
            ++ coverageBundleSmokeSpecs
          )
      );
      selectSpecs = names: map (name: specByName.${name}) names;
    in
    {
      default = mkSystemChecks system (selectSpecs checkTiers.defaultSpecNames);
      heavy = mkSystemChecks system (selectSpecs checkTiers.heavySpecNames);
    };
in
{
  imports = [
    (inputs.flake-parts.lib.mkTransposedPerSystemModule {
      name = "heavyChecks";
      option = lib.mkOption {
        type = lib.types.lazyAttrsOf lib.types.package;
        default = { };
        description = "Heavy non-default check derivations that are intentionally excluded from nix flake check.";
      };
      file = ./tests.nix;
    })
  ];

  perSystem =
    { system, ... }:
    let
      pkgs = pkgsFor system;
      testLib = import ./test-lib.nix { inherit inputs lib; };
      specCheckSets = mkSpecChecks system;
      inherit (testLib)
        autoDiscoveredCoverageSurfaces
        baseTestConfig
        evalTestSpec
        mountTmpfsRoots
        mkCoverageManifestCheck
        mkFeatureTest
        mkHmRuntimeCheck
        mkRuntimeCheck
        mkVmCheck
        mkHostBuildCheck
        ;
      routerFlake = import ./router.nix { inherit inputs; };
      routerPerSystem = routerFlake.perSystem {
        inherit pkgs lib system;
      };
      repoFixtureRoot = builtins.path {
        path = ../.;
        name = "sinnix-runtime-fixture-root";
      };
      availableDefaultCheckNames =
        map (name: "nixos-${name}") checkTiers.defaultSpecNames ++ checkTiers.defaultAuxCheckNames;
      availableHeavyCheckNames =
        map (name: "nixos-${name}") checkTiers.heavySpecNames
        ++ checkTiers.runtimeCheckNames
        ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux checkTiers.vmCheckNames
        ++ lib.optionals (system == "x86_64-linux") checkTiers.hostBuildCheckNames;
      scriptPkgs = (import ./scripts.nix { inherit inputs pkgs; }).packageSet;
      cliPolylogueRuntimeSpec = mkFeatureTest {
        name = "cli-polylogue-runtime";
        feature = "sinnix.features.cli.polylogue.enable";
        assertions = _config: [ ];
      };
      cliTaskTrackingRuntimeSpec = mkFeatureTest {
        name = "cli-task-tracking-runtime";
        feature = "sinnix.features.cli.task-tracking.enable";
        extraModules = [
          (
            { config, ... }:
            {
              home-manager.users.${config.sinnix.user.name}.programs.zsh.enable = true;
            }
          )
        ];
        assertions = _config: [ ];
      };
      devAgentRestoreRuntimeSpec = mkFeatureTest {
        name = "dev-agent-restore-runtime";
        feature = "sinnix.features.dev.agentRestore.enable";
        assertions = _config: [ ];
      };
      devGitRuntimeSpec = mkFeatureTest {
        name = "dev-git-runtime";
        feature = "sinnix.features.dev.git.enable";
        assertions = _config: [ ];
      };
      devLanguagesRuntimeSpec = mkFeatureTest {
        name = "dev-languages-runtime";
        feature = "sinnix.features.dev.languages.enable";
        assertions = _config: [ ];
      };
      devAgentToolsRuntimeSpec = mkFeatureTest {
        name = "dev-agent-tools-runtime";
        feature = "sinnix.features.dev.agentTools.enable";
        extraModules = [
          (
            { ... }:
            {
              sinnix.features.dev.shell.enable = true;
              sinnix.features.dev.mcp-servers.enable = true;
            }
          )
        ];
        assertions = _config: [ ];
      };
      agentToolsFixture = {
        spec = devAgentToolsRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.expect
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.zsh
        ];
        homeFiles = [
          ".codex/config.toml"
          ".gemini/settings.json"
          ".local/bin/forge"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-playwright"
          ".local/bin/mcp-polylogue"
          "forge/.forge.toml"
          "forge/.mcp.json"
          "forge/skills"
        ];
        xdgConfigFiles = [
          "claude/settings.json"
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

          mkdir -p \
            "$HOME/forge/agents" \
            "$HOME/forge/commands" \
            "$HOME/forge/logs/requests" \
            "$HOME/forge/snapshots"

          cat > "$HOME/forge/.credentials.json" <<'EOF'
          []
          EOF
        '';
      };
      backupRuntimeEval = evalTestSpec system {
        name = "backup-borg-hook-runtime";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          (
            { ... }:
            {
              networking.hostName = "backup-runtime";
            }
          )
        ];
        assertions = _config: [ ];
      };
      rewriteBackupHook =
        hook: replacements:
        builtins.replaceStrings (map (replacement: replacement.from) replacements) (map (
          replacement: replacement.to
        ) replacements) hook;
      realmBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.realm.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm";
            }
          ];
      persistBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.persist.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/persist/.btrfs/snapshot";
              to = "$TMPDIR/persist-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/persist";
              to = "$TMPDIR/bind/persist";
            }
          ];
      missingRealmBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.realm.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-empty";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm-empty";
            }
          ];
      hostCommandNames = [
        "check-all"
        "check-heavy"
        "host-smoke-all"
        "host-smoke-terminal"
        "host-smoke-services"
      ];
      coverageEvidence = {
        features = {
          "cli.polylogue".runtime = [ "cli-polylogue-runtime" ];
          "cli.task-tracking".runtime = [ "cli-task-tracking-runtime" ];
          "desktop.terminal" = {
            runtime = [ "terminal-capture-runtime" ];
            pty = [ "terminal-capture-runtime" ];
            host = [ "host-smoke-terminal" ];
          };
          "dev.agentRestore".runtime = [ "dev-agent-restore-runtime" ];
          "dev.git".runtime = [ "dev-git-runtime" ];
          "dev.languages".runtime = [ "dev-languages-runtime" ];
          "dev.agentTools" = {
            runtime = [ "dev-agent-tools-runtime" ];
            pty = [ "dev-agent-tools-pty" ];
            host = [ "host-smoke-terminal" ];
          };
          "dev.mcp-servers".runtime = [ "dev-agent-tools-runtime" ];
        };
        services = {
          "below".vm = [ "below-vm" ];
          "polylogue".vm = [ "polylogue-vm" ];
          "power-watchdog".host = [ "host-smoke-services" ];
          "sentinel".vm = [ "sentinel-vm" ];
          "sinex".build = [ "host-sinnix-prime-build" ];
          "terminal-capture" = {
            runtime = [
              "terminal-capture-runtime"
              "terminal-capture-runtime-failure"
            ];
            pty = [ "terminal-capture-runtime" ];
          };
          "transmission".vm = [ "transmission-vm" ];
        };
        bundles = {
          "desktop".build = [ "host-sinnix-prime-build" ];
        };
        hosts = {
          "sinnix-prime" = {
            build = [ "host-sinnix-prime-build" ];
            host = [ "host-smoke-all" ];
          };
          "sinnix-ethereal".build = [ "host-sinnix-ethereal-build" ];
        };
        outputs = {
          "router-config" = {
            eval = [ "nixos-router-config-evaluates" ];
            build = [ "router-config-build" ];
          };
        };
      };
      coverageManifest = mkCoverageManifestCheck system {
        name = "coverage-manifest";
        inherit coverage;
        discovered = autoDiscoveredCoverageSurfaces;
        evidence = coverageEvidence;
        availableChecks = availableDefaultCheckNames ++ availableHeavyCheckNames;
        availableCommands = hostCommandNames;
      };
      hostBuildChecks = lib.optionalAttrs (system == "x86_64-linux") {
        host-sinnix-prime-build = mkHostBuildCheck system {
          name = "sinnix-prime";
          modules = [
            { imports = [ ../hosts/sinnix-prime ]; }
          ];
        };
        host-sinnix-ethereal-build = mkHostBuildCheck system {
          name = "sinnix-ethereal";
          modules = [
            inputs.disko.nixosModules.disko
            { imports = [ ../hosts/sinnix-ethereal ]; }
          ];
        };
      };
      routerBuildChecks = {
        router-config-build =
          pkgs.runCommand "router-config-build-check"
            {
              routerConfig = routerPerSystem.packages.router-config;
            }
            ''
              touch "$out"
            '';
      };
      vmChecks = lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
        below-vm = mkVmCheck system {
          name = "below-vm";
          nodes.machine = {
            sinnix.services.below.enable = true;
          };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("below.service")
            machine.succeed("test \"$(systemctl show below.service -P SubState)\" = running")
            machine.wait_until_succeeds("test -d /var/log/below/store")
            machine.wait_until_succeeds("find /var/log/below/store -type f | grep -q .")
          '';
        };
        polylogue-vm = mkVmCheck system {
          name = "polylogue-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.services.polylogue.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")

            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.wait_for_unit("polylogue-run.timer", "sinity")

            machine.succeed(f"{as_user} systemctl --user start polylogue-run.service")
            machine.wait_until_succeeds(f"{as_user} systemctl --user show polylogue-run.service -P Result | grep -qx success")

            machine.wait_until_succeeds(f"{as_user} test -s /home/sinity/.local/share/polylogue/polylogue.db")
            machine.wait_until_succeeds(
                f"""{as_user} sh -lc 'find "$HOME/.local/share/polylogue/runs" -type f | grep -q .'"""
            )
            machine.succeed(
                f"""{as_user} sh -lc 'latest_run=$(ls -1t "$HOME/.local/share/polylogue/runs"/run-*.json | head -n 1); jq -e ".run_id != null and .duration_ms >= 0 and .counts.acquire_errors >= 0" "$latest_run" >/dev/null'"""
            )
          '';
        };
        sentinel-vm = mkVmCheck system {
          name = "sentinel-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.services.sentinel = {
                enable = true;
                enableCorrectiveActions = false;
                enableNotifications = false;
                intervalSec = 5;
              };
              systemd.tmpfiles.rules = [
                "d /persist/.btrfs/snapshot 0755 root root -"
              ];
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("sinnix-sentinel.timer")

            machine.succeed("systemctl start sinnix-sentinel.service")
            machine.succeed("test \"$(systemctl show sinnix-sentinel.service -P Result)\" = success")

            machine.wait_until_succeeds("test -s /run/sinnix/health.json")
            machine.succeed("test -d /var/log/sinnix-sentinel")
            machine.succeed("test -d /var/lib/sinnix-sentinel")
            machine.succeed("test -s /var/log/sinnix-sentinel/events.jsonl")

            machine.succeed("jq -e '(.summary.ok + .summary.warn + .summary.fail) >= 1 and any(.checks[]; .category == \"services\")' /run/sinnix/health.json >/dev/null")
            machine.succeed("head -n 1 /var/log/sinnix-sentinel/events.jsonl | jq -e '.source == \"sinnix-sentinel\"' >/dev/null")
          '';
        };
        transmission-vm = mkVmCheck system {
          name = "transmission-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [
                pkgs.curl
                pkgs.jq
              ];
              sinnix.services.transmission.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("transmission.service")
            machine.wait_until_succeeds("test -d /neo-outer-realm/inbox")

            machine.wait_until_succeeds("curl -sS -D /tmp/transmission.headers -o /tmp/transmission.body http://127.0.0.1:9091/transmission/rpc || true; grep -q '409 Conflict' /tmp/transmission.headers")
            machine.succeed('session_id=$(awk -F": " \'/X-Transmission-Session-Id/ {print $2}\' /tmp/transmission.headers | tr -d "\\r"); test -n "$session_id"')
          '';
        };
      };
      backupBorgHookRuntime = mkRuntimeCheck system {
        name = "backup-borg-hook-runtime-check";
        nativeBuildInputs = [
          pkgs.bash
          pkgs.coreutils
          pkgs.findutils
          pkgs.gnugrep
        ];
        script = ''
          mkdir -p \
            "$TMPDIR/mock-bin" \
            "$TMPDIR/logs" \
            "$TMPDIR/bind" \
            "$TMPDIR/realm-snapshots" \
            "$TMPDIR/persist-snapshots" \
            "$TMPDIR/realm-empty"

          cat > "$TMPDIR/mock-bin/mountpoint" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          path="''${@: -1}"
          if [ -e "$path/.mounted" ]; then
            exit 0
          fi
          exit 1
          EOF

          cat > "$TMPDIR/mock-bin/mount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          source_path="''${@: -2:1}"
          target_path="''${@: -1}"
          mkdir -p "$target_path"
          touch "$target_path/.mounted"
          printf '%s => %s\n' "$source_path" "$target_path" >> "$TMPDIR/logs/mount.log"
          EOF

          cat > "$TMPDIR/mock-bin/umount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          target_path="$1"
          rm -f "$target_path/.mounted"
          printf '%s\n' "$target_path" >> "$TMPDIR/logs/umount.log"
          EOF

          chmod +x "$TMPDIR/mock-bin/mountpoint" "$TMPDIR/mock-bin/mount" "$TMPDIR/mock-bin/umount"

          mkdir -p \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T010000" \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T011500" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T010000" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T011500"

          cat > "$TMPDIR/run-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${realmBorgPreHook}
          EOF

          cat > "$TMPDIR/run-persist-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${persistBorgPreHook}
          EOF

          cat > "$TMPDIR/run-missing-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${missingRealmBorgPreHook}
          EOF

          chmod +x \
            "$TMPDIR/run-realm-hook.sh" \
            "$TMPDIR/run-persist-hook.sh" \
            "$TMPDIR/run-missing-realm-hook.sh"

          "$TMPDIR/run-realm-hook.sh"
          "$TMPDIR/run-persist-hook.sh"

          grep -q "$TMPDIR/realm-snapshots/realm.2026-04-02T011500 => $TMPDIR/bind/realm" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/persist-snapshots/persist.2026-04-02T011500 => $TMPDIR/bind/persist" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/bind/realm" "$TMPDIR/logs/umount.log"
          grep -q "$TMPDIR/bind/persist" "$TMPDIR/logs/umount.log"

          set +e
          "$TMPDIR/run-missing-realm-hook.sh" > "$TMPDIR/missing-realm.log" 2>&1
          missing_status=$?
          set -e

          test "$missing_status" -eq 1
          grep -q "No realm snapshot found" "$TMPDIR/missing-realm.log"
        '';
      };
      terminalCaptureRuntime =
        pkgs.runCommand "sinnix-terminal-capture-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            export PATH="${
              lib.makeBinPath [
                pkgs.asciinema_3
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"
            mkdir -p "$HOME" "$TMPDIR/captures"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            transcript="$TMPDIR/terminal-capture-runtime.typescript"

            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_CAST_FILE='$TMPDIR/poison.cast' \
              SINNIX_CAPTURE_EVENTS_FILE='$TMPDIR/poison.events.jsonl' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              SINNIX_CAPTURE_SESSION_ID='poison-session' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"

            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"

            session_dir="$(dirname "$session_json")"
            session_id="$(basename "$session_dir")"
            month_dir="$(dirname "$session_dir")"
            day_dir="$(basename "$month_dir")"
            year_month_dir="$(dirname "$month_dir")"
            month_name="$(basename "$year_month_dir")"
            year_name="$(basename "$(dirname "$year_month_dir")")"

            test "$day_dir" != "$session_id"
            [[ "$year_name" =~ ^[0-9]{4}$ ]]
            [[ "$month_name" =~ ^[0-9]{2}$ ]]
            [[ "$day_dir" =~ ^[0-9]{2}$ ]]
            test "$cast_file" = "$session_dir/session.cast"
            test "$events_json" = "$session_dir/events.jsonl"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              .session_id == $session_id and
              (.started_at_ms | type) == "number" and
              (.command_count | type) == "number" and
              .command_count >= 1 and
              .event_count >= 4 and
              .cast_path == $cast_path and
              .events_path == $events_path and
              .host == "terminal-capture-test" and
              .terminal == "kitty" and
              .exit_reason == "shell_exit" and
              .cleanup_escalated == false and
              .recorder_exit_code == 0 and
              (.session_id | test(",") | not) and
              .session_id != "poison-session" and
              .cast_path != $poison_cast and
              .events_path != $poison_events
            ' \
              --arg session_id "$session_id" \
              --arg cast_path "$cast_file" \
              --arg events_path "$events_json" \
              --arg poison_cast "$TMPDIR/poison.cast" \
              --arg poison_events "$TMPDIR/poison.events.jsonl" \
              "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end" and
              ([.[] | select(.type == "command_start")] | length) >= 1 and
              all(.[]; .session_id != "poison-session")
            ' "$events_json" >/dev/null

            touch "$out"
          '';
      terminalCaptureRuntimeFailure =
        pkgs.runCommand "sinnix-terminal-capture-runtime-failure-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME" "$TMPDIR/captures" "$TMPDIR/bin"

            cat > "$TMPDIR/bin/asciinema" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail

            command_path=""
            output_path=""

            while (($#)); do
              case "$1" in
                rec)
                  shift
                  ;;
                --command)
                  command_path="$2"
                  shift 2
                  ;;
                --*)
                  if (($# >= 2)) && [[ "$2" != --* ]]; then
                    shift 2
                  else
                    shift
                  fi
                  ;;
                *)
                  output_path="$1"
                  shift
                  ;;
              esac
            done

            test -n "$command_path"
            test -n "$output_path"
            mkdir -p "$(dirname "$output_path")"
            printf '{"version": 3, "width": 80, "height": 24, "timestamp": 0}\n' > "$output_path"
            "$command_path"
            exit 42
            EOF
            chmod +x "$TMPDIR/bin/asciinema"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            export PATH="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"

            transcript="$TMPDIR/terminal-capture-runtime-failure.typescript"

            set +e
            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"
            status=$?
            set -e

            test "$status" -eq 42
            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              (.started_at_ms | type) == "number" and
              .exit_reason == "shell_exit" and
              .exit_code == 0 and
              .recorder_exit_code == 42 and
              .cleanup_escalated == false and
              .command_count >= 1 and
              .event_count >= 4 and
              (.session_id | test(",") | not)
            ' "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end"
            ' "$events_json" >/dev/null

            touch "$out"
          '';
      devAgentToolsRuntime = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-runtime-check";
          nativeBuildInputs = builtins.filter (pkg: pkg != pkgs.expect) agentToolsFixture.nativeBuildInputs;
          script = ''
            test -L "$HOME/.codex/config.toml"
            test -L "$(readlink "$HOME/.codex/config.toml")"
            test -L "$HOME/.gemini/settings.json"
            test -L "$(readlink "$HOME/.gemini/settings.json")"
            test -L "$HOME/.config/claude/settings.json"
            test -L "$(readlink "$HOME/.config/claude/settings.json")"
            test -L "$HOME/forge/.forge.toml"
            test -L "$(readlink "$HOME/forge/.forge.toml")"

            cp ${lib.escapeShellArg (toString (repoFixtureRoot + "/dots/forge/.forge.toml"))} \
              "$TMPDIR/forge.toml"
            rm "$HOME/forge/.forge.toml"
            cp "$TMPDIR/forge.toml" "$HOME/forge/.forge.toml"

            "$HOME/.local/bin/forge" --version | grep -q '^forge '
            "$HOME/.local/bin/forge" config get model | grep -qx 'gpt-5.4'

            "$HOME/.local/bin/forge" env > "$TMPDIR/forge-env.txt"
            grep -q '~/forge/agents' "$TMPDIR/forge-env.txt"
            grep -q '~/forge/.forge_history' "$TMPDIR/forge-env.txt"
            grep -q '~/forge/logs' "$TMPDIR/forge-env.txt"
            grep -q '~/forge/snapshots' "$TMPDIR/forge-env.txt"
            grep -q '~/forge/permissions.yaml' "$TMPDIR/forge-env.txt"

            jq -e '
              .mcpServers.context7.url == "https://mcp.context7.com/mcp" and
              .mcpServers.firecrawl.command == "mcp-firecrawl" and
              .mcpServers.playwright.command == "mcp-playwright" and
              .mcpServers.playwright.args == ["--headless"] and
              .mcpServers.polylogue.command == "mcp-polylogue"
            ' "$HOME/forge/.mcp.json" >/dev/null

            ${pkgs.zsh}/bin/zsh -ic '[[ -n "$_FORGE_PLUGIN_LOADED" ]]'
            ${pkgs.zsh}/bin/zsh -ic '[[ -n "$_FORGE_THEME_LOADED" ]]'
            ${pkgs.zsh}/bin/zsh -ic '[[ "$_FORGE_BIN" == "$HOME/.local/bin/forge" ]]'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^M" | grep -q "forge-accept-line"'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^J" | grep -q "forge-accept-line"'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^I" | grep -q "forge-completion"'
          '';
        }
      );
      cliPolylogueRuntime = mkHmRuntimeCheck system {
        name = "cli-polylogue-runtime-check";
        spec = cliPolylogueRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          polylogue --help | grep -q '^Usage: polylogue'
          polylogue sources --help | grep -q 'List configured sources'
          polylogue-python - <<'EOF'
          import sys
          print(sys.executable)
          EOF
        '';
      };
      cliTaskTrackingRuntime = mkHmRuntimeCheck system {
        name = "cli-task-tracking-runtime-check";
        spec = cliTaskTrackingRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.taskwarrior3
          pkgs.timewarrior
          pkgs.zsh
        ];
        fixtureAssets = [
          {
            source = repoFixtureRoot + "/dots/taskwarrior/taskrc";
            target = ".config/task/taskrc";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
          {
            source = repoFixtureRoot + "/dots/timewarrior/timewarrior.cfg";
            target = ".config/timewarrior/timewarrior.cfg";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
          {
            source = repoFixtureRoot + "/dots/timewarrior/extensions";
            target = ".config/timewarrior/extensions";
            recursive = true;
          }
        ];
        rewriteFiles = [
          {
            target = ".zshrc";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
        ];
        useHmZshrc = true;
        setup = ''
          export PATH="${
            lib.makeBinPath [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.taskwarrior3
              pkgs.timewarrior
              pkgs.zsh
            ]
          }:$PATH"
          mkdir -p \
            "$HOME/.config/task" \
            "$HOME/.config/timewarrior/extensions" \
            "$HOME/.task" \
            "$HOME/.local/share/timewarrior"
        '';
        script = ''
            task diagnostics > "$TMPDIR/task.diagnostics"
            grep -q "$HOME/.config/task/taskrc" "$TMPDIR/task.diagnostics"
            grep -q '${repoFixtureRoot}/dots/taskwarrior/hooks' "$TMPDIR/task.diagnostics"

            timew diagnostics > "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.config/timewarrior/timewarrior.cfg" "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.local/share/timewarrior" "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.config/timewarrior/extensions" "$TMPDIR/timew.diagnostics"

          AGENT_NAME=codex AGENT_SESSION_ID=test-session ${pkgs.zsh}/bin/zsh -ic '
            alias ta | grep -q "task add"
            alias twstart | grep -q "timew start"
            type agent_project >/dev/null
            [[ "$(agent_project)" == "agent.codex.test-session" ]]
            type atr >/dev/null
          '
        '';
      };
      devAgentRestoreRuntime = mkHmRuntimeCheck system {
        name = "dev-agent-restore-runtime-check";
        spec = devAgentRestoreRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.python3
          pkgs.systemd
        ];
        homeFiles = [ ".local/bin/sinnix-agent-session-restore" ];
        rewriteFiles = [
          {
            target = ".local/bin/sinnix-agent-session-restore";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
        ];
        setup = ''
          export PATH="${
            lib.makeBinPath [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
              pkgs.systemd
            ]
          }:$PATH"
          mkdir -p "$TMPDIR/captures"
        '';
        script = ''
          "$HOME/.local/bin/sinnix-agent-session-restore" --help | grep -q 'Restore interrupted Codex/Claude/Gemini terminal sessions.'
          "$HOME/.local/bin/sinnix-agent-session-restore" \
            --capture-root "$TMPDIR/captures" \
            --state-file "$TMPDIR/state.json" \
            plan --json | jq -e '.candidates == []' >/dev/null
        '';
      };
      devGitRuntime = mkHmRuntimeCheck system {
        name = "dev-git-runtime-check";
        spec = devGitRuntimeSpec;
        nativeBuildInputs = [
          pkgs.delta
          pkgs.git
          pkgs.gnugrep
        ];
        homeFiles = [ ".config/git/ignore_global" ];
        xdgConfigFiles = [ "git/config" ];
        script = ''
          git config --global --get init.defaultBranch | grep -qx 'master'
          git config --global --get merge.conflictStyle | grep -qx 'zdiff3'
          git config --global --get pull.rebase | grep -qx 'true'
          git config --global --get rerere.enabled | grep -qx 'true'
          git config --global --get credential.https://github.com.helper | grep -q '/run/agenix/github-token'
          grep -q '^AGENTS.md$' "$HOME/.config/git/ignore_global"
          delta --version >/dev/null
        '';
      };
      devLanguagesRuntime = mkHmRuntimeCheck system {
        name = "dev-languages-runtime-check";
        spec = devLanguagesRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          python --version >/dev/null
          node --version >/dev/null
          sqlite3 --version >/dev/null
          gh --version >/dev/null
          forge --version | grep -q '^forge '
        '';
      };
      devAgentToolsPty = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-pty-check";
          script = ''
            cat > "$TMPDIR/forge-pty.expect" <<'EOF'
            log_user 1
            log_file -noappend "$env(TMPDIR)/forge-pty.log"
            set timeout 20

            spawn env HOME=$env(HOME) PATH=$env(PATH) SHELL=$env(SHELL) TERM=$env(TERM) TERM_PROGRAM=$env(TERM_PROGRAM) TERM_PROGRAM_VERSION=$env(TERM_PROGRAM_VERSION) ZDOTDIR=$env(ZDOTDIR) ${pkgs.zsh}/bin/zsh -i
            after 3000
            send_user "forge-pty: shell spawned\n"
            send "print READY\r"
            expect {
              -re {READY} {}
              timeout { exit 1 }
            }

            send_user "forge-pty: sending :env\n"
            send ":env\r"
            expect {
              -re {TOOL CONFIGURATION} {}
              timeout { exit 1 }
            }
            expect {
              -re {debug requests} {}
              timeout { exit 1 }
            }

            send "exit\r"
            expect eof
            EOF

            TMPDIR="$TMPDIR" ${pkgs.expect}/bin/expect -f "$TMPDIR/forge-pty.expect"
            ${pkgs.gnugrep}/bin/grep -q 'TOOL CONFIGURATION' "$TMPDIR/forge-pty.log"
            ${pkgs.gnugrep}/bin/grep -q 'debug requests' "$TMPDIR/forge-pty.log"
          '';
        }
      );
      heavyCheckOutputs =
        specCheckSets.heavy
        // {
          backup-borg-hook-runtime = backupBorgHookRuntime;
          cli-polylogue-runtime = cliPolylogueRuntime;
          cli-task-tracking-runtime = cliTaskTrackingRuntime;
          dev-agent-restore-runtime = devAgentRestoreRuntime;
          dev-agent-tools-pty = devAgentToolsPty;
          dev-agent-tools-runtime = devAgentToolsRuntime;
          dev-git-runtime = devGitRuntime;
          dev-languages-runtime = devLanguagesRuntime;
          terminal-capture-runtime = terminalCaptureRuntime;
          terminal-capture-runtime-failure = terminalCaptureRuntimeFailure;
        }
        // vmChecks
        // hostBuildChecks;
    in
    {
      checks =
        specCheckSets.default
        // {
          coverage-manifest = coverageManifest;
        }
        // routerBuildChecks;

      heavyChecks = heavyCheckOutputs;
    };
}
