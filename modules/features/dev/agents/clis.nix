# AI agent CLI wrappers (claude/codex/gemini/grok/agy/hermes), shared skills, and
# per-agent runtime state. Wrapper-builder machinery lives in backends.nix.
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
        scriptPkgs.sinnix-egress-scan
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

      jsonFormat = pkgs.formats.json { };
      yamlFormat = pkgs.formats.yaml { };
      inherit (helpers.data) mcpRegistry agentLanes;
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
            default = "gpt-5.6-terra";
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
          # transcription engine serves the estate. The hub ignores the model
          # field -- it has one engine -- but the name is kept honest rather
          # than left saying "whisper-1" about something that is not whisper.
          # api_key is a dummy literal: the hub is
          # unauthenticated loopback-only (the sk-local convention used by the
          # other local OpenAI-compatible lanes in flake/data/agent-lanes.nix).
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
      # Base (non-profile) `hermes` config — not a registry lane.
      hermesConfigFile = mkHermesConfig {
        name = "default";
        toolsets = [ "hermes-cli" ];
      };
      # One mkHermesConfig call per flake/data/agent-lanes.nix hermesProfiles
      # entry, keyed by profile name (research/orchestrate/mirror/muse/local).
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
      ) agentLanes.hermesProfiles;
      # Extra launch-time shell for hermes-<name> wrappers whose model uses a
      # custom endpoint: OPENAI_BASE_URL comes from the profile's own
      # `model.base_url`; OPENAI_API_KEY from an agenix secret
      # (`preludeSecret`) or a static loopback token (`apiKeyLiteral`).
      hermesWrapperExtraPrelude =
        name: profile:
        if profile ? preludeSecret then
          ''
            ${lib.sinnix.mkSecretLookup {
              secretName = profile.preludeSecret;
              varName = "OPENAI_API_KEY";
              caller = "hermes-${name}";
            }}
            export OPENAI_BASE_URL="${profile.model.base_url}"
          ''
        else if profile ? apiKeyLiteral then
          ''
            export OPENAI_BASE_URL="${profile.model.base_url}"
            export OPENAI_API_KEY="${profile.apiKeyLiteral}"
          ''
        else
          "";
      # Registry-driven MCP config consumed via `claude --mcp-config`.
      # Claude Code 2.x does NOT read `mcpServers` from settings.json — only
      # `.mcp.json` (project), `~/.claude.json` (user), or `--mcp-config <file>`
      # recognise stdio servers.
      #
      # Lanes share MCP tiers (deepseek/local reuse "full"'s file), so this
      # builds one config per distinct `mcpProfile` value, not one per lane.
      claudeMcpFileBaseName = mcpProfile: if mcpProfile == "full" then "mcp" else "mcp-${mcpProfile}";
      claudeMcpProfiles = lib.unique (
        lib.mapAttrsToList (_: lane: lane.mcpProfile) agentLanes.claudeLanes
      );
      claudeMcpConfigFilesByProfile = lib.genAttrs claudeMcpProfiles (
        mcpProfile:
        jsonFormat.generate "claude-${claudeMcpFileBaseName mcpProfile}.json" {
          mcpServers = lib.mapAttrs mcpRegistry.renderClaudeServer (
            mcpRegistry.selectClientServersForProfile mcpProfile "claude"
          );
        }
      );
      inherit
        (import ./skill-farm.nix {
          inherit lib pkgs;
          dotsRoot = sinnixCfg.paths.dotsRoot;
        })
        sharedSkillFarm
        ;
      # Runs the given launcher under sinnix-scope's agent slice unless already
      # scoped (see scripts/sinnix-agent-scope-exec).
      agentScopeExec = "${scriptPkgs.sinnix-agent-scope-exec}/bin/sinnix-agent-scope-exec";

      backends = import ./backends.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          agentRuntimePath
          hermesRuntimePath
          agentScopeExec
          sinnixCfg
          user
          ;
      };
      inherit (backends)
        mkNpmBootstrap
        mkClaudeBackendEnv
        mkCodexBackendEnv
        mkClaudeCodeWrapper
        mkCodexWrapper
        mkGrokWrapper
        mkAntigravityWrapper
        hermesBootstrap
        ensureHermes
        mkHermesWrapper
        ;
    in
    {
      sinnix.features.dev.agentTools.hermesConfigSource = hermesConfigFile;
      sinnix.features.dev.agentTools.hermesProfileConfigSources = hermesProfileConfigFiles;
      # Durable Claude Code policy (hooks, permissions, env) ships as the
      # top-precedence managed settings file. The source is the live dots
      # checkout, not a store copy, so policy edits propagate instantly.
      environment.etc."claude-code/managed-settings.json".source =
        "${sinnixCfg.paths.dotsRoot}/claude/managed-settings.json";
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
          {
            directory = ".local/state/muse-code";
            mode = "0700";
          }
          # Muse Code auth (Meta OAuth + api key) and settings, including the
          # local model_catalog row for the gateway-served contributor model.
          {
            directory = ".config/muse";
            mode = "0700";
          }
          ".local/state/sinnix/agent-jobs"
          {
            directory = ".grok";
            mode = "0700";
          }
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
            scriptPkgs.sinnix-agent-scope-exec
            scriptPkgs.chatgpt-share-export
            scriptPkgs.sinnix-agent-control-mcp
            scriptPkgs.sinnix-attention
            scriptPkgs.sinnix-context-handoff
            scriptPkgs.sinnix-claude-judge
            scriptPkgs.sinnix-vacuity-sampler
            scriptPkgs.sinnix-agent-profile-benchmark
          ];

          systemd.user.services.sinnix-vacuity-judge = {
            Unit.Description = "Process queued bounded agent-vacuity samples";
            Service = {
              Type = "oneshot";
              ExecStart = "${scriptPkgs.sinnix-vacuity-sampler}/bin/sinnix-vacuity-sampler judge-once";
            };
          };
          systemd.user.timers.sinnix-vacuity-judge = {
            Unit.Description = "Timer for bounded agent-vacuity judgments";
            Timer = {
              OnBootSec = "10min";
              OnUnitActiveSec = "15min";
              AccuracySec = "1min";
            };
            Install.WantedBy = [ "timers.target" ];
          };

          programs.zsh = {
            # Derived from flake/data/agent-lanes.nix: every generated wrapper
            # gets a self-alias (its own binName). Exceptions are remapped by
            # hand below — they have no registry lane, or point at a
            # differently-named one.
            shellAliases =
              let
                selfAlias = binName: lib.nameValuePair binName "~/.local/bin/${binName}";
              in
              (lib.listToAttrs (
                lib.concatMap (
                  name: lib.optional (name != "lean") (selfAlias agentLanes.claudeLanes.${name}.binName)
                ) (lib.attrNames agentLanes.claudeLanes)
              ))
              // (lib.listToAttrs (
                map (name: selfAlias agentLanes.codexLanes.${name}.binName) (lib.attrNames agentLanes.codexLanes)
              ))
              // (lib.listToAttrs (
                map (name: lib.nameValuePair "hermes-${name}" "~/.local/bin/hermes-${name}") (
                  lib.attrNames agentLanes.hermesProfiles
                )
              ))
              // (lib.listToAttrs (map selfAlias (lib.attrNames agentLanes.museLanes)))
              // {
                # `claude` routes through claude-lean, never a bare
                # ~/.local/bin/claude: Claude Code's native local-installer
                # claims that literal path and clobbers any symlink there on
                # auto-update. Suffixed names are never touched.
                claude = "~/.local/bin/claude-lean";
                gemini = "~/.local/bin/gemini";
                grok = "~/.local/bin/grok-sinnix";
                agy = "~/.local/bin/agy-sinnix";
                hermes = "~/.local/bin/hermes";
                hermes-acp = "~/.local/bin/hermes-acp";
                hermes-update = "~/.local/bin/hermes-update";
                muse = "~/.local/bin/muse-code";
              };
          };

          xdg.configFile = {
            # Claude hooks are NOT registered here: settings.json references
            # them dots-direct (dots/claude/hooks/*.sh), so a new hook file
            # is live the moment it exists — no rebuild, no registration.
            "claude/CLAUDE.md".source = mkDotsFile "/claude/CLAUDE.md";
            "claude/skills" = {
              source = sharedSkillFarm;
              force = true;
            };
          }
          # Registry-driven MCP configs consumed by the claude wrapper, one
          # per distinct claudeLanes mcpProfile ("mcp"/"mcp-lean"/"mcp-browser").
          // lib.mapAttrs' (
            mcpProfile: file:
            lib.nameValuePair "claude/${claudeMcpFileBaseName mcpProfile}.json" { source = file; }
          ) claudeMcpConfigFilesByProfile;

          home.activation.claudeSymlink = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p $HOME/.config/claude
            ln -sfn .config/claude $HOME/.claude
            # settings.json is a plain writable file: the harness persists UI
            # state (model, effort, plugin toggles) into it, so a repo symlink
            # would keep the tracked tree dirty. Durable policy lives in
            # /etc/claude-code/managed-settings.json instead. If a symlink is
            # found, its content is kept minus exactly the keys the managed
            # file carries (derived from that file, so the two layers cannot
            # drift into double-firing hooks). The seed is the fresh-machine
            # case only.
            _claude_settings="$HOME/.config/claude/settings.json"
            _claude_managed="${sinnixCfg.paths.dotsRoot}/claude/managed-settings.json"
            if [ -L "$_claude_settings" ]; then
              _claude_old="$(readlink -f "$_claude_settings" || true)"
              rm "$_claude_settings"
              if [ -f "$_claude_old" ]; then
                ${pkgs.jq}/bin/jq --slurpfile m "$_claude_managed" \
                  'delpaths([$m[0] | keys[] | [.]])' "$_claude_old" \
                  > "$_claude_settings"
              fi
            fi
            if [ ! -f "$_claude_settings" ]; then
              cp ${sinnixCfg.paths.dotsRoot}/claude/settings-seed.json "$_claude_settings"
            fi
            chmod 600 "$_claude_settings"
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
          # Codex/Gemini read the global instruction file directly; CLAUDE.md is
          # flat (no @-transclusion), so a symlink suffices and can never go
          # stale between activations.
          home.activation.linkGlobalAgentInstructions = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
            mkdir -p "$HOME/.codex" "$HOME/.gemini"
            ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.codex/AGENTS.md"
            ln -sfn "$HOME/.config/claude/CLAUDE.md" "$HOME/.gemini/GEMINI.md"
          '';

          # A single merged home.file set: static entries below plus one
          # generated entry per flake/data/agent-lanes.nix lane
          # (claude/codex/hermes/muse). It must stay one `//`-merged
          # assignment: a direct `home.file = {...}` alongside sibling
          # `home.file."x" = ...` bindings in the same attrset literal is a
          # duplicate-definition error, not a merge.
          home.file =
            # One entry per claudeLanes lane (full/lean/browser get no
            # extraEnv; deepseek/local layer a backend switch via
            # backends.nix's mkClaudeBackendEnv).
            (lib.mapAttrs' (
              name: lane:
              lib.nameValuePair ".local/bin/${lane.binName}" (
                mkClaudeCodeWrapper (
                  {
                    mcpConfigName = claudeMcpFileBaseName lane.mcpProfile;
                  }
                  // lib.optionalAttrs (lane ? env) {
                    extraEnv = mkClaudeBackendEnv {
                      inherit name;
                      inherit (lane) model;
                      inherit (lane.env) baseUrl authToken;
                    };
                  }
                )
              )
            ) agentLanes.claudeLanes)
            # One entry per codexLanes lane. The layered <profile>.config.toml
            # (client-profiles.nix) carries model + model_provider + the MCP
            # table; the wrapper only supplies the provider API key env.
            // (lib.mapAttrs' (
              name: lane:
              lib.nameValuePair ".local/bin/${lane.binName}" (
                mkCodexWrapper (
                  {
                    profile = lane.mcpProfile;
                  }
                  // lib.optionalAttrs (lane ? env) {
                    extraEnv = mkCodexBackendEnv ({ inherit name; } // lane.env);
                  }
                )
              )
            ) agentLanes.codexLanes)
            # One entry per hermesProfiles lane.
            // (lib.mapAttrs' (
              name: profile:
              lib.nameValuePair ".local/bin/hermes-${name}" (mkHermesWrapper {
                profile = name;
                extraPrelude = hermesWrapperExtraPrelude name profile;
              })
            ) agentLanes.hermesProfiles)
            # museLanes: thin passthrough wrappers around packaged scripts.
            // (lib.mapAttrs' (
              name: lane:
              lib.nameValuePair ".local/bin/${name}" {
                source = "${scriptPkgs.${lane.script}}/bin/${lane.script}";
                force = true;
              }
            ) agentLanes.museLanes)
            // {
              ".local/bin/gemini" = {
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

              # Vendor-managed CLIs self-update in place. Keep their canonical
              # binaries untouched and route use through distinct Nix-managed
              # wrappers so launches share agent.slice containment.
              ".local/bin/grok-sinnix" = mkGrokWrapper;
              ".local/bin/agy-sinnix" = mkAntigravityWrapper;

              ".config/hermes/skills" = {
                source = sharedSkillFarm;
                force = true;
              };
              # Base (non-profile) hermes command — not a registry lane.
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
      ];
    };
} args
