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
  };
  meta.dotfiles = {
    configFile = {
      "ripgrep-all/config.jsonc" = "ripgrep-all/config.jsonc";
      "marimo/marimo.toml" = "marimo/marimo.toml";
    };
    homeFile = { };
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
      # shape as the user's live Chrome, but against a private persistent profile.
      # It is headless by default; set SINNIX_AGENT_CHROME_HEADLESS=0 when a
      # visible private browser window is desired for operator inspection.
      mcpChromeDevtoolsPrivateBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private" ''
        set -euo pipefail
        profile_dir="''${SINNIX_AGENT_CHROME_PROFILE:-$HOME/.local/share/sinnix-browser/chrome-devtools-private}"
        viewport="''${SINNIX_AGENT_CHROME_VIEWPORT:-1440x1000}"
        headless="''${SINNIX_AGENT_CHROME_HEADLESS:-1}"
        chrome_bin="''${SINNIX_AGENT_CHROME_EXECUTABLE:-${pkgs.google-chrome}/bin/google-chrome-stable}"
        mkdir -p "$profile_dir"
        if [ ! -x "$chrome_bin" ]; then
          echo "SINNIX_AGENT_CHROME_EXECUTABLE does not name an executable Chrome: $chrome_bin" >&2
          exit 2
        fi

        args=(
          --executablePath "$chrome_bin"
          --userDataDir "$profile_dir"
          --viewport "$viewport"
          --no-usage-statistics
        )
        if [ "$headless" != "0" ]; then
          args+=(--headless)
        fi

        exec ${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools "''${args[@]}" "$@"
      '';
      mcpChromeDevtoolsPrivateVisibleBin = pkgs.writeShellScriptBin "mcp-chrome-devtools-private-visible" ''
        set -euo pipefail
        export SINNIX_AGENT_CHROME_HEADLESS=0
        exec ${mcpChromeDevtoolsPrivateBin}/bin/mcp-chrome-devtools-private "$@"
      '';
      mcpSweepBin = pkgs.writeShellScriptBin "sinnix-mcp-sweep" ''
                set -euo pipefail

                dry_run=0
                quiet=0
                orphans_only=0
                while [ "$#" -gt 0 ]; do
                  case "$1" in
                    --dry-run) dry_run=1 ;;
                    --quiet) quiet=1 ;;
                    --orphans-only) orphans_only=1 ;;
                    --help)
                      cat <<'EOF'
        Usage: sinnix-mcp-sweep [--orphans-only] [--dry-run] [--quiet]

        Reap orphaned MCP and language-server helper processes left behind by agent
        session exits. Writes JSONL evidence to
        /realm/data/captures/machine/agent-mcp-sweep/sweep.jsonl.
        EOF
                      exit 0
                      ;;
                    *)
                      echo "sinnix-mcp-sweep: unknown argument: $1" >&2
                      exit 2
                      ;;
                  esac
                  shift
                done

                capture_dir="''${SINNIX_MCP_SWEEP_CAPTURE_DIR:-/realm/data/captures/machine/agent-mcp-sweep}"
                if ! mkdir -p "$capture_dir" 2>/dev/null; then
                  capture_dir="''${XDG_STATE_HOME:-$HOME/.local/state}/sinnix/agent-mcp-sweep"
                  mkdir -p "$capture_dir"
                fi
                log_file="$capture_dir/sweep.jsonl"
                user_manager_pid="$(systemctl --user show --property=MainPID --value 2>/dev/null || true)"
                now="$(${pkgs.coreutils}/bin/date -u +%Y-%m-%dT%H:%M:%SZ)"
                host="$(${pkgs.nettools}/bin/hostname 2>/dev/null || echo unknown)"
                killed=0
                matched=0

                is_candidate() {
                  case "$1" in
                    *"serena start-mcp-server"*|*"codebase-memory-mcp"*|*"mcp-polylogue"*|*"mcp-lynchpin"*|*"typescript-language-server --stdio"*|*"tsserver.js"*|*"typingsInstaller.js"*|*"pyright-langserver --stdio"*|*"rust-analyzer"*)
                      return 0
                      ;;
                    *)
                      return 1
                      ;;
                  esac
                }

                is_orphan() {
                  [ "$1" = "1" ] || { [ -n "$user_manager_pid" ] && [ "$1" = "$user_manager_pid" ]; }
                }

                ${pkgs.procps}/bin/ps -eo pid=,ppid=,rss=,comm=,args= |
                  while read -r pid ppid rss comm args; do
                    [ -n "''${pid:-}" ] || continue
                    is_candidate "$args" || continue
                    matched=$((matched + 1))
                    action="keep"
                    reason="attached"
                    if is_orphan "$ppid"; then
                      reason="orphaned"
                      action="kill"
                    elif [ "$orphans_only" -eq 0 ]; then
                      reason="matched"
                    fi

                    if [ "$action" = "kill" ]; then
                      if [ "$dry_run" -eq 0 ]; then
                        kill -TERM "$pid" 2>/dev/null || true
                      fi
                      killed=$((killed + 1))
                    fi

                    ${pkgs.jq}/bin/jq -cn \
                      --arg ts "$now" \
                      --arg host "$host" \
                      --arg pid "$pid" \
                      --arg ppid "$ppid" \
                      --arg rss_kib "$rss" \
                      --arg comm "$comm" \
                      --arg action "$action" \
                      --arg reason "$reason" \
                      --arg args "$args" \
                      '{ts:$ts,host:$host,pid:($pid|tonumber),ppid:($ppid|tonumber),rss_kib:($rss_kib|tonumber),comm:$comm,action:$action,reason:$reason,args:$args}' \
                      >> "$log_file"

                    if [ "$quiet" -eq 0 ]; then
                      printf '%s pid=%s ppid=%s rss=%sKiB %s %s\n' "$action" "$pid" "$ppid" "$rss" "$comm" "$reason"
                    fi
                  done
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
          PreToolUse = [
            {
              matcher = "Bash";
              hooks = [
                {
                  type = "command";
                  command = "serena-hooks remind --client=codex";
                }
              ];
            }
          ];
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
                  command = "serena-hooks activate --client=codex";
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
                  command = "serena-hooks cleanup --client=codex";
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
      sharedSkillNames = [
        "adversarial-loop"
        "agent-orchestration"
        "analyze"
        "assured-close"
        "desktop-control-plane"
        "enhance"
        "evidence-harness"
        "greedy-batching"
        "history-cleanup"
        "lynchpin"
        "meta"
        "recap"
        "swarm"
      ];
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
                run chmod 644 "$HOME/.codex/config.toml"
                run chmod 644 "$HOME/.codex/full.config.toml"
                run chmod 644 "$HOME/.codex/lean.config.toml"
                run chmod 644 "$HOME/.codex/evidence.config.toml"
                run chmod 644 "$HOME/.codex/browser.config.toml"
                run chmod 644 "$HOME/.codex/deepseek.config.toml"
                run chmod 644 "$HOME/.codex/local.config.toml"
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
            ".codex/hooks.json" = {
              source = codexHooksFile;
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
              source = "${mcpSweepBin}/bin/sinnix-mcp-sweep";
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
              executable = true;
              force = true;
              text = ''
                #!${pkgs.runtimeShell}
                set -euo pipefail

                have() {
                  if command -v "$1" >/dev/null 2>&1; then
                    printf 'ok\t%s\t%s\n' "$1" "$(command -v "$1")"
                  else
                    printf 'missing\t%s\t\n' "$1"
                  fi
                }

                service() {
                  manager="$1"
                  unit="$2"
                  if [ "$manager" = "user" ]; then
                    if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
                      printf 'ok\t%s\tuser:%s\n' "$unit" "$(systemctl --user is-active "$unit" 2>/dev/null || printf unknown)"
                    else
                      printf 'missing\t%s\tuser:%s\n' "$unit" "$(systemctl --user is-active "$unit" 2>/dev/null || printf inactive)"
                    fi
                  elif systemctl is-active --quiet "$unit" 2>/dev/null; then
                    printf 'ok\t%s\tsystem:%s\n' "$unit" "$(systemctl is-active "$unit" 2>/dev/null || printf unknown)"
                  else
                    printf 'missing\t%s\tsystem:%s\n' "$unit" "$(systemctl is-active "$unit" 2>/dev/null || printf inactive)"
                  fi
                }

                path_probe() {
                  name="$1"
                  path="$2"
                  if [ -e "$path" ]; then
                    printf 'ok\t%s\t%s\n' "$name" "$path"
                  else
                    printf 'missing\t%s\t%s\n' "$name" "$path"
                  fi
                }

                printf 'surface\tname\tdetail\n'
                for cmd in \
                  codebase-memory-mcp \
                  mcp-chrome-devtools \
                  mcp-chrome-devtools-private \
                  mcp-chrome-devtools-private-visible \
                  mcp-lynchpin \
                  mcp-polylogue \
                  polylogue \
                  polylogued \
                  serena \
                  sinnix-observe \
                  sinnix-chrome-control \
                  sinnix-hypr-control \
                  sinnix-keyboard-control \
                  sinnix-kitty-control \
                  sinnix-screenshot-control \
                  hyprctl \
                  wtype \
                  wl-copy \
                  wl-paste \
                  grim \
                  grimblast \
                  slurp \
                  websocat; do
                  have "$cmd"
                done

                if command -v curl >/dev/null 2>&1; then
                  if version="$(curl -fsS --max-time 2 http://127.0.0.1:9222/json/version 2>/dev/null)"; then
                    browser="$(printf '%s' "$version" | ${pkgs.jq}/bin/jq -r '.Browser // "unknown"' 2>/dev/null || printf unknown)"
                    printf 'ok\tchrome-cdp\t%s\n' "$browser"
                  else
                    printf 'missing\tchrome-cdp\thttp://127.0.0.1:9222 (launch Google Chrome through the Sinnix desktop entry)\n'
                  fi
                else
                  printf 'missing\tchrome-cdp\tcurl unavailable\n'
                fi
                if [ -x ${pkgs.google-chrome}/bin/google-chrome-stable ]; then
                  printf 'ok\tchrome-private-executable\t%s\n' '${pkgs.google-chrome}/bin/google-chrome-stable'
                else
                  printf 'missing\tchrome-private-executable\t%s\n' '${pkgs.google-chrome}/bin/google-chrome-stable'
                fi

                if command -v hyprctl >/dev/null 2>&1; then
                  if active="$(hyprctl -j activewindow 2>/dev/null | ${pkgs.jq}/bin/jq -r '[.class // "", .title // ""] | @tsv' 2>/dev/null)"; then
                    printf 'ok\thypr-active-window\t%s\n' "$active"
                  else
                    printf 'missing\thypr-active-window\thyprctl query failed\n'
                  fi
                fi

                service user polylogued.service
                service system machine-telemetry.service
                service system lynchpin-materialize.timer
                service system sinex.service

                path_probe runtime-inventory /etc/sinnix/runtime-inventory.json
                path_probe codex-full-profile "$HOME/.codex/full.config.toml"
                path_probe codex-lean-profile "$HOME/.codex/lean.config.toml"
                path_probe codex-browser-profile "$HOME/.codex/browser.config.toml"
                path_probe claude-full-profile "$HOME/.config/claude/mcp.json"
                path_probe claude-lean-profile "$HOME/.config/claude/mcp-lean.json"
                path_probe claude-browser-profile "$HOME/.config/claude/mcp-browser.json"
                path_probe polylogue-archive "$HOME/.local/share/polylogue"
                path_probe machine-telemetry /realm/data/captures/machine
                path_probe screenshots /realm/data/captures/screenshot
                path_probe kitty-scrollback /realm/data/captures/kitty-scrollback
                path_probe chatlog-exports /realm/data/exports/chatlog
              '';
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
                exec ${scriptPkgs.polylogue-cli}/bin/polylogue-mcp "$@"
              '';
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
        };
    };
} args
