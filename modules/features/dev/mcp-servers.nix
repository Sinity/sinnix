# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (Firecrawl, Chrome DevTools, Polylogue, Lynchpin)
# - MCP server registry and explicit lean/full/browser agent profiles
# - Claude/Codex/Gemini dotfile linking and integration
# - System monitoring tools (htop)
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "mcp-servers"
  ];
  description = "MCP servers and AI tool integration";
  extraOptions = {
    # Internal: exposes the generated Codex config derivation for test assertions
    # so tests can read its content without re-instantiating nixpkgs.
    codexConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex config derivation (for tests)";
    };
    codexFullConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex full profile derivation (for tests)";
    };
    codexLeanConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex lean profile derivation (for tests)";
    };
    codexEvidenceConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex evidence profile derivation (for tests)";
    };
    codexBrowserConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex browser profile derivation (for tests)";
    };
    codexDeepseekConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex deepseek profile derivation (for tests)";
    };
    codexLocalConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex local profile derivation (for tests)";
    };
    codexHooksSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Codex hooks derivation (for tests)";
    };
  };
  meta.dotfiles = {
    configFile = {
      "ripgrep-all/config.jsonc" = "ripgrep-all/config.jsonc";
      "marimo/marimo.toml" = "marimo/marimo.toml";
    };
  };
  configFn =
    {
      config,
      cfg,
      lib,
      pkgs,
      inputs,
      helpers,
      user,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      jsonFormat = pkgs.formats.json { };
      tomlFormat = pkgs.formats.toml { };
      inherit (helpers.data) mcpRegistry;
      firecrawlSecretPath = lib.attrByPath [ "sinnix" "secrets" "paths" "firecrawl-api-key" ] null config;
      mkRuntimeSecretExports =
        secretEnv:
        lib.concatStringsSep "\n" (
          lib.mapAttrsToList (envName: secretPath: ''
            if [ -z "''${${envName}:-}" ] && [ -r ${secretPath} ]; then
              export ${envName}="$(<${secretPath})"
            fi
          '') secretEnv
        );
      mkMcpWrapper =
        name:
        {
          command,
          args ? [ ],
          runtimeEnv ? { },
          runtimeSecretEnv ? { },
        }:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
          ${lib.concatStringsSep "\n" (
            lib.mapAttrsToList (envName: value: "export ${envName}=${lib.escapeShellArg value}") runtimeEnv
          )}
          ${mkRuntimeSecretExports runtimeSecretEnv}
          exec ${lib.escapeShellArgs ([ command ] ++ args)} "$@"
        '';
      mcpFirecrawlBin = mkMcpWrapper "mcp-firecrawl" {
        command = "${scriptPkgs.mcp-firecrawl}/bin/mcp-firecrawl";
        runtimeSecretEnv = lib.optionalAttrs (firecrawlSecretPath != null) {
          FIRECRAWL_API_KEY = firecrawlSecretPath;
        };
      };
      # Chrome DevTools MCP — vendored npm package built via mkNodeCliPackage.
      # Attaches to the user's running Chrome on the loopback debug port
      # (configured by modules/features/desktop/browser.nix:47). Private agent
      # browsers use mcp-chrome-devtools-private instead of this live profile.
      mcpChromeDevtoolsBin = pkgs.writeShellScriptBin "mcp-chrome-devtools" ''
        set -euo pipefail
        target="''${SINNIX_CHROME_DEVTOOLS_URL-http://127.0.0.1:9222}"
        if [ -z "$target" ]; then
          echo "SINNIX_CHROME_DEVTOOLS_URL must name a Chrome DevTools endpoint" >&2
          exit 2
        fi
        exec ${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools \
          --browserUrl "$target" \
          "$@"
      '';
      # Agent-owned Chrome DevTools MCP. This gives agents the same DevTools tool
      # shape as the user's live Chrome, but against a private persistent profile
      # seeded from live Chrome state before launch. It stays separate from the
      # shell CDP helper's private profile so concurrent MCP and shell browser
      # sessions cannot fight over a Chrome profile lock. It is headless by
      # default; set SINNIX_AGENT_CHROME_HEADLESS=0 when a visible private
      # browser window is desired for operator inspection.
      mcpChromeDevtoolsPrivateBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private" ''
        set -euo pipefail
        export SINNIX_MCP_CHROME_DEVTOOLS_BIN=${lib.escapeShellArg "${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools"}
        exec ${scriptPkgs.sinnix-mcp-chrome-devtools-private}/bin/sinnix-mcp-chrome-devtools-private "$@"
      '';
      mcpChromeDevtoolsPrivateVisibleBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private-visible" ''
        set -euo pipefail
        export SINNIX_AGENT_CHROME_HEADLESS=0
        exec ${mcpChromeDevtoolsPrivateBin}/bin/mcp-chrome-devtools-private "$@"
      '';
      desktopControlScripts = inputs.self + "/dots/_ai/skills/desktop-control-plane/scripts";
      serenaVersion = "1.5.3";
      serenaRuntimePath = lib.makeBinPath [
        pkgs.bash
        pkgs.coreutils
        pkgs.git
        pkgs.gnugrep
        pkgs.nodejs_22
        pkgs.pyright
        pkgs.python313
        pkgs.rust-analyzer
        pkgs.uv
      ];
      mkSerenaWrapper = commandName: ''
        #!${pkgs.runtimeShell}
        set -euo pipefail

        state_dir="$HOME/.local/state/serena"
        lock_dir="$state_dir/install.lock"
        export SERENA_HOME="''${SERENA_HOME:-$HOME/.local/share/serena}"
        export UV_CACHE_DIR="''${UV_CACHE_DIR:-$HOME/.cache/uv}"
        export UV_TOOL_DIR="$state_dir/tools"
        export UV_TOOL_BIN_DIR="$state_dir/bin"
        export PATH="${serenaRuntimePath}:$UV_TOOL_BIN_DIR:$PATH"
        unset PYTHONPATH PYTHONHOME PYTHONBREAKPOINT PYTHONUSERBASE VIRTUAL_ENV
        export PYTHONNOUSERSITE=1

        if [ "${commandName}" = "serena-hooks" ] && [ "''${1:-}" = "remind" ]; then
          exit 0
        fi

        mkdir -p "$SERENA_HOME" "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"

        sync_serena_config() {
          if [ -f "$SERENA_HOME/serena_config.yml" ] \
            && ! ${pkgs.diffutils}/bin/cmp -s ${lib.escapeShellArg (toString serenaConfigFile)} "$SERENA_HOME/serena_config.yml" \
            && [ ! -f "$SERENA_HOME/serena_config.yml.hm-bak" ]; then
            cp "$SERENA_HOME/serena_config.yml" "$SERENA_HOME/serena_config.yml.hm-bak"
          fi
          cp ${lib.escapeShellArg (toString serenaConfigFile)} "$SERENA_HOME/serena_config.yml"
          chmod 644 "$SERENA_HOME/serena_config.yml"
        }

        install_serena() {
          ${pkgs.uv}/bin/uv tool install \
            --python ${pkgs.python313}/bin/python3 \
            --no-python-downloads \
            ${lib.escapeShellArg "serena-agent==${serenaVersion}"}
        }

        reinstall_serena() {
          ${pkgs.uv}/bin/uv tool install \
            --python ${pkgs.python313}/bin/python3 \
            --no-python-downloads \
            --force \
            ${lib.escapeShellArg "serena-agent==${serenaVersion}"}
        }

        remove_stale_install_lock() {
          if [ -f "$lock_dir/pid" ] && ! kill -0 "$(cat "$lock_dir/pid")" 2>/dev/null; then
            rm -rf "$lock_dir"
            return 0
          fi
          return 1
        }

        wait_for_install_lock() {
          while [ -d "$lock_dir" ]; do
            if remove_stale_install_lock; then
              continue
            fi
            sleep 0.1
          done
        }

        with_install_lock() {
          while ! mkdir "$lock_dir" 2>/dev/null; do
            if remove_stale_install_lock; then
              continue
            fi
            sleep 0.1
          done
          trap 'rm -rf "$lock_dir"' EXIT
          printf '%s\n' "$$" > "$lock_dir/pid"
          "$@"
          rm -rf "$lock_dir"
          trap - EXIT
        }

        serena_version_matches() {
          "$UV_TOOL_BIN_DIR/serena" --version 2>/dev/null | grep -Fq ${lib.escapeShellArg serenaVersion}
        }

        serena_ready() {
          wait_for_install_lock
          [ -x "$UV_TOOL_BIN_DIR/serena" ] \
            && [ -x "$UV_TOOL_BIN_DIR/${commandName}" ] \
            && serena_version_matches
        }

        repair_serena() {
          if [ ! -x "$UV_TOOL_BIN_DIR/serena" ] || [ ! -x "$UV_TOOL_BIN_DIR/${commandName}" ]; then
            install_serena || reinstall_serena
            return 0
          fi
          if ! serena_version_matches; then
            reinstall_serena
          fi
        }

        ensure_serena() {
          if serena_ready; then
            return 0
          fi

          with_install_lock repair_serena
          wait_for_install_lock
        }

        sync_serena_config
        ensure_serena

        if [ ! -x "$UV_TOOL_BIN_DIR/${commandName}" ]; then
          echo "serena wrapper: $UV_TOOL_BIN_DIR/${commandName} is unavailable after bootstrap" >&2
          if [ "${commandName}" = "serena-hooks" ]; then
            exit 0
          fi
          exit 127
        fi

        wait_for_install_lock
        exec "$UV_TOOL_BIN_DIR/${commandName}" "$@"
      '';
      serenaConfigFile = pkgs.writeText "serena_config.yml" ''
        language_backend: LSP
        line_ending: lf
        gui_log_window: false
        web_dashboard: true
        web_dashboard_open_on_launch: false
        web_dashboard_listen_address: 127.0.0.1
        web_dashboard_trusted_hosts:
          - 127.0.0.1
          - localhost
        log_level: 20
        trace_lsp_communication: false
        tool_timeout: 240
        default_max_tool_answer_chars: 150000
        symbol_info_budget: 10
        base_modes:
          - interactive
          - editing
        default_modes: []
        ignored_paths:
          - .direnv
          - .git
          - .venv
          - node_modules
          - target
          - __pycache__
        project_serena_folder_location: "$projectDir/.serena"
        projects:
          - /realm/project/sinex
          - /realm/project/polylogue
          - /realm/project/sinity-lynchpin
          - /realm/project/sinnix
      '';
      codebaseMemoryUiLauncher = pkgs.writeShellScript "codebase-memory-ui" ''
        set -euo pipefail
        export CBM_CACHE_DIR="''${CBM_CACHE_DIR:-$HOME/.local/share/codebase-memory-mcp}"
        mkdir -p "$CBM_CACHE_DIR"
        exec ${
          scriptPkgs."codebase-memory-mcp"
        }/bin/codebase-memory-mcp --ui=true --port=9749 < <(${pkgs.coreutils}/bin/sleep infinity)
      '';
      codexHooksFile = jsonFormat.generate "codex-hooks.json" {
        hooks = {
          SessionStart = [
            {
              matcher = "startup|resume";
              hooks = [
                {
                  type = "command";
                  command = "sinnix-mcp-sweep --orphans-only --quiet";
                }
                {
                  type = "command";
                  command = ''
                    case "''${SINNIX_CODEX_PROFILE:-full}" in
                      full|browser|deepseek|local) serena-hooks activate --client=codex ;;
                    esac
                  '';
                }
                {
                  type = "command";
                  command = "bd-prime-if-present";
                }
                {
                  type = "command";
                  command = "sessionstart-sinex-recall";
                }
              ];
            }
          ];
          UserPromptSubmit = [
            {
              hooks = [
                {
                  type = "command";
                  command = "bd-prime-if-present --memories-only";
                }
              ];
            }
          ];
          Stop = [
            {
              hooks = [
                {
                  type = "command";
                  command = "sinnix-mcp-sweep --orphans-only --quiet";
                }
                {
                  type = "command";
                  command = ''
                    case "''${SINNIX_CODEX_PROFILE:-full}" in
                      full|browser|deepseek|local) serena-hooks cleanup --client=codex ;;
                    esac
                  '';
                }
              ];
            }
          ];
        };
      };
      inherit (mcpRegistry)
        selectClientServersForProfile
        renderCodexServer
        renderGeminiServer
        ;
      mkCodexProfileFile =
        profile:
        tomlFormat.generate "codex-${profile}-profile.toml" {
          mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile profile "codex");
        };
      codexConfigFile = inputs.self + "/dots/codex/config.toml";
      codexFullConfigFile = mkCodexProfileFile "full";
      codexLeanConfigFile = mkCodexProfileFile "lean";
      codexEvidenceConfigFile = mkCodexProfileFile "evidence";
      codexBrowserConfigFile = mkCodexProfileFile "browser";
      # Alternate-backend profiles: the full MCP table plus a model + provider.
      # `codex --profile <name>` layers these over ~/.codex/config.toml, so the
      # provider's base_url/env_key and the chosen model override the gpt-5.5
      # defaults while keeping the full MCP surface.
      mkCodexBackendProfileFile =
        name: extra:
        tomlFormat.generate "codex-${name}-profile.toml" (
          {
            mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile "full" "codex");
          }
          // extra
        );
      codexDeepseekConfigFile = mkCodexBackendProfileFile "deepseek" {
        model = "deepseek-chat";
        model_provider = "deepseek";
        model_providers.deepseek = {
          name = "DeepSeek";
          base_url = "https://api.deepseek.com/v1";
          env_key = "DEEPSEEK_API_KEY";
        };
      };
      # Local models via the LiteLLM gateway (modules/services/litellm.nix). Keep
      # `model` in sync with that module's model_list.
      codexLocalConfigFile = mkCodexBackendProfileFile "local" {
        model = "local-llama";
        model_provider = "local";
        model_providers.local = {
          name = "Local (LiteLLM)";
          base_url = "http://127.0.0.1:4000/v1";
          env_key = "LITELLM_LOCAL_KEY";
        };
      };
      sharedSkillNames = import ../../../flake/data/shared-agent-skills.nix;
      sharedSkillLinks = map (name: {
        inherit name;
        path = inputs.self + "/dots/_ai/skills/${name}";
      }) sharedSkillNames;
      sharedSkillFarm = pkgs.linkFarm "sinnix-shared-agent-skills" sharedSkillLinks;
      codexSkillFarm = pkgs.linkFarm "sinnix-codex-agent-skills" (
        sharedSkillLinks
        ++ [
          {
            name = ".system";
            path = inputs.self + "/dots/codex/skills/.system";
          }
        ]
      );
      geminiSettingsBase = removeAttrs (builtins.fromJSON (
        builtins.readFile (inputs.self + "/dots/gemini/settings.json")
      )) [ "mcpServers" ];
      geminiSettingsFile = jsonFormat.generate "gemini-settings.json" (
        geminiSettingsBase
        // {
          mcpServers = lib.mapAttrs renderGeminiServer (selectClientServersForProfile "full" "gemini");
        }
      );
    in
    {
      sinnix.features.dev.mcp-servers.codexConfigSource = codexConfigFile;
      sinnix.features.dev.mcp-servers.codexFullConfigSource = codexFullConfigFile;
      sinnix.features.dev.mcp-servers.codexLeanConfigSource = codexLeanConfigFile;
      sinnix.features.dev.mcp-servers.codexEvidenceConfigSource = codexEvidenceConfigFile;
      sinnix.features.dev.mcp-servers.codexBrowserConfigSource = codexBrowserConfigFile;
      sinnix.features.dev.mcp-servers.codexDeepseekConfigSource = codexDeepseekConfigFile;
      sinnix.features.dev.mcp-servers.codexLocalConfigSource = codexLocalConfigFile;
      sinnix.features.dev.mcp-servers.codexHooksSource = codexHooksFile;
      sinnix.persistence.home.directories = [
        {
          directory = ".local/share/codebase-memory-mcp";
          mode = "0700";
        }
        {
          directory = ".local/share/serena";
          mode = "0700";
        }
        ".local/state/serena"
      ];

      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          secretPaths,
          ...
        }:
        {
          programs.htop = {
            enable = true;
            settings = {
              detailed_cpu_time = true;
              hide_kernel_threads = true;
              hide_userland_threads = true;
              show_cpu_frequency = true;
              show_cpu_temperature = true;
              tree_view = true;
              sort_key = "PERCENT_CPU";
              show_program_path = false;
              highlight_base_name = true;
              highlight_megabytes = true;
              # Cumulative metrics and cleaner tree
              account_guest_in_cpu_meter = true;
              all_branches_collapsed = true;
              find_comm_in_free_text = true;
            };
          };

          home = {
            activation = {
              restoreConfigstore = lib.mkIf (secretPaths ? "configstore-update-notifier") (
                lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                  if [ -f ${secretPaths."configstore-update-notifier"} ]; then
                    mkdir -p "$HOME/.config/configstore"
                    rm -rf "$HOME/.config/configstore/update-notifier-@google"
                    if ! ${pkgs.gzip}/bin/gzip -dc ${
                      secretPaths."configstore-update-notifier"
                    } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config/configstore"; then
                      echo "warning: unable to restore configstore notifier archive" >&2
                    fi
                  fi
                ''
              );
              # Write config.toml as a writable file (not a symlink to the Nix
              # store) so Codex can append runtime state such as project trust
              # entries. Nix settings always win on activation; trust entries
              # added between rebuilds survive until the next switch.
              codexConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                run cp ${codexConfigFile} "$HOME/.codex/config.toml"
                run cp ${codexFullConfigFile} "$HOME/.codex/full.config.toml"
                run cp ${codexLeanConfigFile} "$HOME/.codex/lean.config.toml"
                run cp ${codexEvidenceConfigFile} "$HOME/.codex/evidence.config.toml"
                run cp ${codexBrowserConfigFile} "$HOME/.codex/browser.config.toml"
                run cp ${codexDeepseekConfigFile} "$HOME/.codex/deepseek.config.toml"
                run cp ${codexLocalConfigFile} "$HOME/.codex/local.config.toml"
                run cp ${codexHooksFile} "$HOME/.codex/hooks.json"
                run chmod 644 "$HOME/.codex/config.toml"
                run chmod 644 "$HOME/.codex/full.config.toml"
                run chmod 644 "$HOME/.codex/lean.config.toml"
                run chmod 644 "$HOME/.codex/evidence.config.toml"
                run chmod 644 "$HOME/.codex/browser.config.toml"
                run chmod 644 "$HOME/.codex/deepseek.config.toml"
                run chmod 644 "$HOME/.codex/local.config.toml"
                run chmod 644 "$HOME/.codex/hooks.json"
              '';
              codebaseMemoryMcpConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                run mkdir -p "$HOME/.local/share/codebase-memory-mcp"
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set auto_index true
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set auto_index_limit 50000
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set ui true
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set port 9749
              '';
              serenaConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                run mkdir -p "$HOME/.local/share/serena"
                if [ -f "$HOME/.local/share/serena/serena_config.yml" ] \
                  && ! ${pkgs.diffutils}/bin/cmp -s ${lib.escapeShellArg (toString serenaConfigFile)} "$HOME/.local/share/serena/serena_config.yml"; then
                  run cp "$HOME/.local/share/serena/serena_config.yml" "$HOME/.local/share/serena/serena_config.yml.hm-bak"
                fi
                run cp ${lib.escapeShellArg (toString serenaConfigFile)} "$HOME/.local/share/serena/serena_config.yml"
                run chmod 644 "$HOME/.local/share/serena/serena_config.yml"
              '';
            };
          };

          home.file = {
            ".codex/skills" = {
              source = codexSkillFarm;
              force = true;
            };
            ".gemini/skills" = {
              source = sharedSkillFarm;
              force = true;
            };
            ".gemini/settings.json" = {
              source = geminiSettingsFile;
              force = true;
            };
            ".local/bin/codebase-memory-mcp" = {
              executable = true;
              force = true;
              text = ''
                #!${pkgs.runtimeShell}
                set -euo pipefail
                export CBM_CACHE_DIR="''${CBM_CACHE_DIR:-$HOME/.local/share/codebase-memory-mcp}"
                mkdir -p "$CBM_CACHE_DIR"
                exec ${scriptPkgs."codebase-memory-mcp"}/bin/codebase-memory-mcp "$@"
              '';
            };
            ".local/bin/serena" = {
              executable = true;
              force = true;
              text = mkSerenaWrapper "serena";
            };
            ".local/bin/serena-hooks" = {
              executable = true;
              force = true;
              text = mkSerenaWrapper "serena-hooks";
            };
            ".local/bin/sinnix-mcp-sweep" = {
              source = "${scriptPkgs.sinnix-mcp-sweep}/bin/sinnix-mcp-sweep";
              force = true;
            };
            ".local/bin/bd-prime-if-present" = {
              source = "${scriptPkgs.bd-prime-if-present}/bin/bd-prime-if-present";
              force = true;
            };
            ".local/bin/mcp-firecrawl" = {
              source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
              force = true;
            };
            ".local/bin/mcp-chrome-devtools" = {
              source = "${mcpChromeDevtoolsBin}/bin/mcp-chrome-devtools";
              force = true;
            };
            ".local/bin/mcp-chrome-devtools-private" = {
              source = "${mcpChromeDevtoolsPrivateBin}/bin/mcp-chrome-devtools-private";
              force = true;
            };
            ".local/bin/mcp-chrome-devtools-private-visible" = {
              source = "${mcpChromeDevtoolsPrivateVisibleBin}/bin/mcp-chrome-devtools-private-visible";
              force = true;
            };
            ".local/bin/sinnix-chrome-control" = {
              source = "${desktopControlScripts}/chrome-control.sh";
              force = true;
            };
            ".local/bin/sinnix-hypr-control" = {
              source = "${desktopControlScripts}/hypr-control.sh";
              force = true;
            };
            ".local/bin/sinnix-keyboard-control" = {
              source = "${desktopControlScripts}/keyboard-control.sh";
              force = true;
            };
            ".local/bin/sinnix-kitty-control" = {
              source = "${desktopControlScripts}/kitty-remote-control.sh";
              force = true;
            };
            ".local/bin/sinnix-screenshot-control" = {
              source = "${desktopControlScripts}/screenshot-color-lab.sh";
              force = true;
            };
            ".local/bin/sinnix-agent-status" = {
              source = "${scriptPkgs.sinnix-agent-status}/bin/sinnix-agent-status";
              force = true;
            };
            ".local/bin/mcp-lynchpin" = {
              executable = true;
              force = true;
              text = ''
                #!${pkgs.runtimeShell}
                set -euo pipefail
                export LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
                export LYNCHPIN_LOCAL_ROOT=/realm/project/sinity-lynchpin/.lynchpin
                export PYTHONPATH="$LYNCHPIN_REPO_ROOT''${PYTHONPATH:+:$PYTHONPATH}"
                exec ${scriptPkgs.lynchpin-python}/bin/lynchpin-python -m lynchpin.mcp.cli "$@"
              '';
            };
            ".local/bin/mcp-polylogue" = {
              executable = true;
              force = true;
              text = ''
                #!${pkgs.runtimeShell}
                set -euo pipefail
                # The polylogue repo's .claude/settings.json pins
                # POLYLOGUE_ARCHIVE_ROOT to the cloud-lane fixture
                # (/tmp/polylogue-archive) for CI/cloud agents. That env leaks into
                # locally-launched MCP servers and would point recall at an empty
                # archive. Drop any leaked override that doesn't resolve to a real
                # directory (not just the one known cloud-lane literal — 2026-07-06:
                # an exact-string check alone left a long-lived MCP server stuck
                # pointing at the cloud fixture for its entire process lifetime
                # whenever it had been spawned with the leak present; checking
                # existence instead of one hardcoded path is the same fix generalized,
                # though it still can't un-stick a server process already running with
                # the leak baked into its own inherited environment — that needs the
                # MCP connection itself restarted) so recall resolves the operator's
                # real live archive (an intentional override to any real path is
                # preserved).
                if [ -n "''${POLYLOGUE_ARCHIVE_ROOT:-}" ] && [ ! -d "''${POLYLOGUE_ARCHIVE_ROOT}" ]; then
                  unset POLYLOGUE_ARCHIVE_ROOT
                fi
                exec ${scriptPkgs.polylogue-cli}/bin/polylogue-mcp "$@"
              '';
            };
            ".local/bin/mcp-sinex" = {
              source = "${scriptPkgs.sinnix-mcp-sinex}/bin/sinnix-mcp-sinex";
              force = true;
            };
            ".local/share/polylogue/inbox/chatgpt" = {
              source = config.lib.file.mkOutOfStoreSymlink "/realm/data/exports/chatlog/raw/chatgpt";
              force = true;
            };
            ".local/share/polylogue/inbox/claude" = {
              source = config.lib.file.mkOutOfStoreSymlink "/realm/data/exports/chatlog/raw/claude";
              force = true;
            };
          };

          systemd.user.services.codebase-memory-ui = {
            Unit = {
              Description = "Codebase Memory MCP Web UI";
              After = [ "default.target" ];
            };
            Service = {
              ExecStart = "${codebaseMemoryUiLauncher}";
              Restart = "on-failure";
              RestartSec = 5;
            };
            Install.WantedBy = [ "default.target" ];
          };

          # Session-boundary hooks (Codex/Claude SessionStart+Stop) only reap
          # orphans at session start/end -- a daemon orphaned mid-session (an
          # agent's Bash tool call killed, or a tracking file like
          # .dmypy.json deleted out from under a live daemon) survives
          # unbounded until the next session boundary. This periodic sweep
          # closes that gap structurally, independent of any agent behaving
          # correctly (2026-07-08 incident: 14 orphaned `dmypy run` daemons,
          # ~15GB RSS, accumulated over one session with no session
          # boundary to trigger the existing hook-based sweep).
          systemd.user.services.sinnix-mcp-sweep-periodic = {
            Unit = {
              Description = "Periodically reap orphaned MCP/language-server/dev-daemon processes";
            };
            Service = {
              Type = "oneshot";
              ExecStart = "${scriptPkgs.sinnix-mcp-sweep}/bin/sinnix-mcp-sweep --orphans-only --quiet";
            };
          };
          systemd.user.timers.sinnix-mcp-sweep-periodic = {
            Unit.Description = "Timer for periodic orphaned dev-daemon reaping";
            Timer = {
              OnBootSec = "10min";
              OnUnitActiveSec = "15min";
              AccuracySec = "1min";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
