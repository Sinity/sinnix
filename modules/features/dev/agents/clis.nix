# AI agent CLI wrappers (claude/codex/pi/hermes), shared skills, and
# per-agent runtime state. Wrapper-builder machinery lives in backends.nix;
# everything about pi lives in pi.nix.
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
  extraOptions.hermesConfigSource = lib.mkOption {
    type = lib.types.path;
    internal = true;
    description = "Path to the generated default Hermes configuration (for tests)";
  };
  extraOptions.piSources = lib.mkOption {
    type = lib.types.attrsOf lib.types.path;
    internal = true;
    description = "Paths to the generated pi settings, tool-server config and key-removal script (for tests)";
  };
  extraOptions.hermesProfileConfigSources = lib.mkOption {
    type = lib.types.attrsOf lib.types.path;
    internal = true;
    description = "Paths to generated mode-specific Hermes configurations (for tests)";
  };
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
          portaudio
        ])
      );

      sinnixCfg = config.sinnix;

      # Hook commands and their executables change in the same generation.
      # Other dots links and the private writable client settings stay live.
      claudeManagedSettings = pkgs.writeText "claude-managed-settings.json" (
        builtins.readFile ../../../../dots/claude/managed-settings.json
      );

      # Claude Code persists UI state into settings.json, so it is a private
      # writable file seeded once from this copy, never a link.
      claudeSettingsSeed = pkgs.writeText "claude-settings-seed.json" (
        builtins.readFile ../../../../dots/claude/settings-seed.json
      );

      jsonFormat = pkgs.formats.json { };
      yamlFormat = pkgs.formats.yaml { };
      inherit (helpers.data) mcpRegistry agentProfiles runtimeDefaults;
      hermesMcpServersForProfile =
        mcpProfile:
        lib.mapAttrs mcpRegistry.renderHermesServer (
          mcpRegistry.selectClientServersForProfile mcpProfile "hermes"
        );
      # Default MCP tier for the base (non-profile) `hermes` config and any
      # registry profile that doesn't override `mcpProfile`.
      hermesMcpServers = hermesMcpServersForProfile "evidence";
      mkHermesConfig =
        {
          name,
          toolsets,
          mcpServers ? hermesMcpServers,
          reasoningEffort ? "medium",
          delegation ? { },
          voiceEnabled ? true,
          model ? {
            default = "gpt-6-sol";
            provider = "openai-codex";
          },
        }:
        yamlFormat.generate "hermes-${name}-config.yaml" {
          _config_version = 33;
          inherit model;
          fallback_providers = [
            {
              provider = "gemini";
              model = "gemini-2.5-flash";
            }
          ];
          terminal = {
            backend = "local";
            cwd = ".";
            timeout = 180;
            home_mode = "auto";
          };
          agent = {
            max_turns = 100;
            verify_on_stop = true;
            reasoning_effort = reasoningEffort;
          };
          approvals.mode = "off";
          # Hermes keeps every session. Later releases can delete ended sessions
          # idle past a retention window and ask about it when the disk runs
          # low; an explicit false disables both.
          sessions.auto_prune = false;
          memory = {
            memory_enabled = true;
            user_profile_enabled = true;
            memory_char_limit = 8000;
            user_char_limit = 4500;
            nudge_interval = 10;
            flush_min_turns = 6;
          };
          skills = {
            creation_nudge_interval = 15;
            external_dirs = [
              "/home/${user}/.config/hermes/skills"
              "/home/${user}/.hermes/skills"
            ];
          };
          plugins.enabled = [ "observability/nemo_relay" ];
          # Polylogue's session-start brief comes with the first turn, and a
          # pasted session ID brings its takeover context. The hook is ours,
          # so it is accepted without the first-use prompt.
          hooks.pre_llm_call = [
            {
              command = "polylogue internal hook pre_llm_call --harness hermes";
              timeout = 10;
            }
          ];
          hooks_auto_accept = true;
          delegation = {
            max_iterations = 100;
            max_concurrent_children = 3;
            max_spawn_depth = 1;
          }
          // delegation;
          platform_toolsets.cli = toolsets;
          mcp_servers = mcpServers;
          voice = {
            record_key = "ctrl+b";
            max_recording_seconds = 120;
            auto_tts = voiceEnabled;
            beep_enabled = voiceEnabled;
            silence_threshold = 200;
            silence_duration = 1.2;
          };
          # Points at the shared STT hub (modules/services/stt.nix, Parakeet
          # TDT) rather than hermes's embedded faster-whisper, so one
          # transcription engine serves sinnix. The hub ignores the model
          # field -- it has one engine -- but the name is kept honest rather
          # than left saying "whisper-1" about something that is not whisper.
          # api_key is a dummy literal: the hub is
          # unauthenticated loopback-only (the sk-local convention used by the
          # other local OpenAI-compatible profiles in flake/data/agent-profiles.nix).
          stt = {
            enabled = voiceEnabled;
            provider = "openai";
            openai = {
              base_url = "http://127.0.0.1:8090/v1";
              api_key = "sk-local";
              model = "parakeet-tdt-0.6b-v3";
            };
          };
          # Points at the shared Kokoro-82M TTS hub (modules/services/kokoro.nix)
          # rather than hermes's built-in edge-tts (Microsoft cloud): Kokoro
          # speaks the OpenAI TTS wire shape hermes already supports, so no
          # hermes patch is needed. api_key is a dummy literal — loopback-only.
          tts = {
            provider = "openai";
            openai = {
              base_url = "http://127.0.0.1:8890/v1";
              api_key = "sk-local";
              model = "kokoro";
              voice = "af_bella";
            };
          };
          updates = {
            pre_update_backup = true;
            backup_keep = 5;
            non_interactive_local_changes = "stash";
          };
        };
      # Base (non-profile) `hermes` config — not a registry profile.
      hermesConfigFile = mkHermesConfig {
        name = "default";
        toolsets = [ "hermes-cli" ];
      };
      # One mkHermesConfig call per flake/data/agent-profiles.nix hermesProfiles
      # entry, keyed by profile name (research/mirror/local/...).
      hermesProfileConfigFiles = lib.mapAttrs (
        name: profile:
        mkHermesConfig (
          {
            inherit name;
            toolsets = profile.toolsets;
            mcpServers = hermesMcpServersForProfile (profile.mcpProfile or "evidence");
          }
          // lib.optionalAttrs (profile ? reasoningEffort) { inherit (profile) reasoningEffort; }
          // lib.optionalAttrs (profile ? delegation) { inherit (profile) delegation; }
          // lib.optionalAttrs (profile ? voiceEnabled) { inherit (profile) voiceEnabled; }
          // lib.optionalAttrs (profile ? model) { inherit (profile) model; }
        )
      ) agentProfiles.hermesProfiles;
      # Extra launch-time shell for hermes-<name> wrappers whose model uses a
      # custom endpoint: OPENAI_BASE_URL comes from the profile's own
      # `model.base_url`; OPENAI_API_KEY from a static loopback token
      # (`apiKeyLiteral`).
      hermesWrapperExtraPrelude =
        _name: profile:
        if profile ? apiKeyLiteral then
          ''
            export OPENAI_BASE_URL="${profile.model.base_url}"
            export OPENAI_API_KEY="${profile.apiKeyLiteral}"
          ''
        else
          "";
      # Registry-driven MCP config consumed via `claude --mcp-config`.
      # Claude Code 2.x does NOT read `mcpServers` from settings.json — only
      # `.mcp.json` (project), `$CLAUDE_CONFIG_DIR/.claude.json` (user), or `--mcp-config <file>`
      # recognise stdio servers.
      #
      claudeMcpConfigFile = jsonFormat.generate "claude-mcp.json" {
        mcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
          mcpRegistry.selectClientServersForProfile "default" "claude"
        );
      };
      backends = import ./backends.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          runtimeDefaults
          agentRuntimePath
          hermesRuntimePath
          sinnixCfg
          user
          ;
      };
      inherit (backends)
        mkClaudeCodeWrapper
        mkCodexWrapper
        agentScopePrelude
        hermesBootstrap
        ensureHermes
        mkHermesWrapper
        ;
      pi = import ./pi.nix {
        inherit
          lib
          pkgs
          mcpRegistry
          agentScopePrelude
          agentRuntimePath
          ;
        inherit (backends) scratchTmpPrelude;
        piPackage = inputs.pi.packages.${pkgs.stdenv.hostPlatform.system}.pi;
        piPackages = scriptPkgs.pi-packages;
        dotsRoot = sinnixCfg.paths.dotsRoot;
      };
    in
    lib.mkMerge [
      {
        sinnix.features.dev.agentTools.hermesConfigSource = hermesConfigFile;
        sinnix.features.dev.agentTools.hermesProfileConfigSources = hermesProfileConfigFiles;
        sinnix.features.dev.agentTools.piSources = {
          inherit (pi) settingsFile mcpConfigFile unsetProviderKeys;
        };
        environment.etc."claude-code/managed-settings.json".source = claudeManagedSettings;
        systemd.tmpfiles.rules = [
          "d /realm/state/codex 0700 ${user} users -"
          "d /realm/state/codex/logs 0700 ${user} users -"
          "d /realm/state/codex/home 0700 ${user} users -"
          "d /realm/state/codex/sqlite 0700 ${user} users -"
          # No_COW applies to files created after it is set; existing
          # databases are copied in, never moved, so they pick it up.
          "h /realm/state/codex/sqlite - - - - +C"
        ];
        # Codex's sessions and SQLite state took most of the root SSD's
        # fsync-driven writes, so its home lives on Realm (plain directories
        # inside the /realm snapshot, so Borg keeps covering them).
        fileSystems."/home/${user}/.codex" = {
          device = "/realm/state/codex/home";
          fsType = "none";
          options = [
            "bind"
            "nofail"
          ];
          depends = [ "/realm" ];
        };
        sinnix.persistence.home = {
          directories = [
            {
              directory = ".config/claude";
              mode = "0700";
            }
            # The Antigravity editor keeps its state and reads its global
            # rules (GEMINI.md) here.
            {
              directory = ".gemini";
              mode = "0700";
            }
            # Pi keeps its sign-ins, sessions and its own settings here.
            {
              directory = ".pi";
              mode = "0700";
            }
            # npm installs survive impermanence cold boots so agents do not
            # re-download on every activation.
            ".local/state/claude-code"
            ".local/state/codex"
            ".hermes"
            # Plannotator's Inbox threads, plan history and review drafts.
            {
              directory = ".local/share/plannotator";
              mode = "0700";
            }
          ];
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
            home.sessionVariables.CLAUDE_CONFIG_DIR = lib.mkDefault "${config.home.homeDirectory}/.config/claude";
            home.packages = [
              scriptPkgs.beads
              scriptPkgs.beads.passthru.dolt
              scriptPkgs.claude-quota
              scriptPkgs.codex-worker
              scriptPkgs.claude-agents
              # Review surface the agents open for the operator; its hooks and
              # Inbox server are declared in managed-settings.json, hooks.nix
              # and the MCP registry, and the hook commands find it on PATH.
              scriptPkgs.plannotator
            ];

            xdg.configFile = {
              "claude/CLAUDE.md" = {
                source = mkDotsFile "/_ai/AGENTS.md";
                force = true;
              };
              "claude/skills" = {
                source = mkDotsFile "/_ai/skills";
                force = true;
              };
            }
            // {
              "claude/mcp.json".source = claudeMcpConfigFile;
            };

            home.activation.claudeSymlink = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              claude_config="$HOME/.config/claude"
              run mkdir -p "$claude_config"
              run chmod 700 "$claude_config"
              if [ ! -e "$claude_config/settings.json" ] && [ ! -L "$claude_config/settings.json" ]; then
                run ${pkgs.coreutils}/bin/install -m 0600 ${claudeSettingsSeed} "$claude_config/settings.json"
              fi
              if [ ! -e "$HOME/.claude" ] && [ ! -L "$HOME/.claude" ]; then
                run ln -s .config/claude "$HOME/.claude"
              fi
            '';
            home.activation.hermesConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              mkdir -p "$HOME/.hermes"
              cp ${hermesConfigFile} "$HOME/.hermes/config.yaml"
              chmod 600 "$HOME/.hermes/config.yaml"

              ${lib.concatMapStringsSep "\n" (name: ''
                mkdir -p "$HOME/.hermes/profiles/${name}"
                ln -sfn ../../auth.json "$HOME/.hermes/profiles/${name}/auth.json"
                ln -sfn ../../.env "$HOME/.hermes/profiles/${name}/.env"
                ln -sfn ../../SOUL.md "$HOME/.hermes/profiles/${name}/SOUL.md"
                cp ${hermesProfileConfigFiles.${name}} "$HOME/.hermes/profiles/${name}/config.yaml"
                chmod 600 "$HOME/.hermes/profiles/${name}/config.yaml"
              '') (lib.attrNames hermesProfileConfigFiles)}
            '';
            # Codex and the Antigravity editor (~/.gemini/GEMINI.md) share the
            # live global instruction source.
            home.activation.piConfig = lib.hm.dag.entryAfter [ "linkGeneration" ] pi.activation;
            home.activation.linkGlobalAgentInstructions = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              mkdir -p "$HOME/.codex" "$HOME/.gemini"
              ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.codex/AGENTS.md"
              ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.gemini/GEMINI.md"
            '';

            # A single merged home.file set: static entries below plus one
            # generated entry per flake/data/agent-profiles.nix profile
            # (claude/codex/hermes). It must stay one `//`-merged
            # assignment: a direct `home.file = {...}` alongside sibling
            # `home.file."x" = ...` bindings in the same attrset literal is a
            # duplicate-definition error, not a merge.
            home.file =
              # The single managed Claude launcher.
              (lib.mapAttrs' (
                name: profile:
                lib.nameValuePair ".local/bin/${profile.binName}" (mkClaudeCodeWrapper {
                  mcpConfigName = "mcp";
                  profile = name;
                })
              ) agentProfiles.claudeProfiles)
              # The single managed Codex launcher.
              // (lib.mapAttrs' (
                _name: profile: lib.nameValuePair ".local/bin/${profile.binName}" mkCodexWrapper
              ) agentProfiles.codexProfiles)
              # One entry per hermesProfiles entry.
              // (lib.mapAttrs' (
                name: profile:
                lib.nameValuePair ".local/bin/hermes-${name}" (mkHermesWrapper {
                  profile = name;
                  extraPrelude = hermesWrapperExtraPrelude name profile;
                })
              ) agentProfiles.hermesProfiles)
              // (lib.mapAttrs' (
                name: launcher: lib.nameValuePair ".local/bin/pi-${name}" launcher
              ) pi.presetLaunchers)
              // {

                ".local/bin/pi" = pi.wrapper;

                ".config/hermes/skills" = {
                  source = mkDotsFile "/_ai/skills";
                  force = true;
                };
                # Base (non-profile) hermes command — not a registry profile.
                ".local/bin/hermes" = mkHermesWrapper { };
                ".local/bin/hermes-acp" = mkHermesWrapper {
                  entrypoint = "hermes-acp";
                };
                ".local/bin/hermes-update" = {
                  text = ''
                    #!/usr/bin/env bash
                    set -euo pipefail

                    ${hermesBootstrap}

                    ${ensureHermes}
                    git -C "$HERMES_INSTALL_DIR" pull --ff-only
                    (
                      cd "$HERMES_INSTALL_DIR"
                      UV_PROJECT_ENVIRONMENT="$HERMES_INSTALL_DIR/venv" uv sync --extra all --extra voice --extra nemo-relay --locked
                    )
                    exec "$HERMES_INSTALL_DIR/venv/bin/hermes" --version
                  '';
                  executable = true;
                  force = true;
                };
              };
          };

        environment.systemPackages = [
          scriptPkgs.beads
          scriptPkgs.beads.passthru.dolt
        ];
      }
    ];
} args
