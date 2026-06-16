# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (Firecrawl, Playwright)
# - MCP server registry (Context7 remote, GitHub, Firecrawl, Playwright, Polylogue)
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
  };
  meta.dotfiles = {
    configFile = {
      "ripgrep-all/config.jsonc" = "ripgrep-all/config.jsonc";
      "marimo/marimo.toml" = "marimo/marimo.toml";
    };
    homeFile = {
      ".codex/skills" = "codex/skills";
      ".gemini/skills" = "_ai/skills";
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
      mcpPlaywrightBin = mkMcpWrapper "mcp-playwright" {
        command = "${pkgs.playwright-mcp}/bin/playwright-mcp";
      };
      # Headed Playwright variant against a persistent dev profile under
      # ~/.local/share/sinnix-browser/playwright-headed. Lets agents drive a
      # real browser session (e.g. for browser-extension dev) instead of a
      # fresh sandbox per call.
      mcpPlaywrightHeadedBin = pkgs.writeShellScriptBin "mcp-playwright-headed" ''
        set -euo pipefail
        profile_dir="''${SINNIX_PLAYWRIGHT_PROFILE:-$HOME/.local/share/sinnix-browser/playwright-headed}"
        mkdir -p "$profile_dir"
        exec ${pkgs.playwright-mcp}/bin/playwright-mcp \
          --user-data-dir "$profile_dir" \
          "$@"
      '';
      # Chrome DevTools MCP — vendored npm package built via mkNodeCliPackage.
      # By default attaches to the user's running Chrome on the loopback debug
      # port (configured by modules/features/desktop/browser.nix:47). Override
      # via SINNIX_CHROME_DEVTOOLS_URL for a different endpoint, or set it to
      # the empty string to let Chrome DevTools MCP launch its own browser.
      mcpChromeDevtoolsBin = pkgs.writeShellScriptBin "mcp-chrome-devtools" ''
        set -euo pipefail
        target="''${SINNIX_CHROME_DEVTOOLS_URL-http://127.0.0.1:9222}"
        if [ -n "$target" ]; then
          exec ${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools \
            --browserUrl "$target" \
            "$@"
        else
          exec ${scriptPkgs.mcp-chrome-devtools}/bin/mcp-chrome-devtools "$@"
        fi
      '';
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

        mkdir -p "$SERENA_HOME" "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"

        install_serena() {
          ${pkgs.uv}/bin/uv tool install \
            --python ${pkgs.python313}/bin/python3 \
            --no-python-downloads \
            --force \
            ${lib.escapeShellArg "serena-agent==${serenaVersion}"}
        }

        serena_ready() {
          [ -x "$UV_TOOL_BIN_DIR/serena" ] \
            && [ -x "$UV_TOOL_BIN_DIR/${commandName}" ] \
            && "$UV_TOOL_BIN_DIR/serena" --version 2>/dev/null | grep -Fq ${lib.escapeShellArg serenaVersion}
        }

        with_install_lock() {
          while ! mkdir "$lock_dir" 2>/dev/null; do
            if [ -f "$lock_dir/pid" ] && ! kill -0 "$(cat "$lock_dir/pid")" 2>/dev/null; then
              rm -rf "$lock_dir"
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

        if ! serena_ready; then
          with_install_lock install_serena
        fi

        if [ ! -x "$UV_TOOL_BIN_DIR/${commandName}" ]; then
          with_install_lock install_serena
        fi

        if [ ! -x "$UV_TOOL_BIN_DIR/${commandName}" ]; then
          echo "serena wrapper: $UV_TOOL_BIN_DIR/${commandName} is unavailable after bootstrap" >&2
          if [ "${commandName}" = "serena-hooks" ]; then
            exit 0
          fi
          exit 127
        fi

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
                  command = "serena-hooks cleanup --client=codex";
                }
              ];
            }
          ];
        };
      };
      inherit (mcpRegistry)
        selectClientServers
        renderCodexServer
        renderGeminiServer
        ;
      codexMcpServers = lib.mapAttrs renderCodexServer (selectClientServers "codex");
      codexMcpConfigFile = tomlFormat.generate "codex-mcp.toml" { mcp_servers = codexMcpServers; };
      codexConfigFile = pkgs.runCommandLocal "codex-config.toml" { } ''
        cat ${inputs.self + "/dots/codex/config.toml"} ${codexMcpConfigFile} > "$out"
      '';
      geminiSettingsBase = removeAttrs (builtins.fromJSON (
        builtins.readFile (inputs.self + "/dots/gemini/settings.json")
      )) [ "mcpServers" ];
      geminiSettingsFile = jsonFormat.generate "gemini-settings.json" (
        geminiSettingsBase
        // {
          mcpServers = lib.mapAttrs renderGeminiServer (selectClientServers "gemini");
        }
      );
    in
    {
      sinnix.features.dev.mcp-servers.codexConfigSource = codexConfigFile;

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
                run cp ${lib.escapeShellArg (toString codexConfigFile)} "$HOME/.codex/config.toml"
                run chmod 644 "$HOME/.codex/config.toml"
              '';
              codebaseMemoryMcpConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                run mkdir -p "$HOME/.local/share/codebase-memory-mcp"
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set auto_index true
                run ${pkgs.coreutils}/bin/env CBM_CACHE_DIR="$HOME/.local/share/codebase-memory-mcp" ${
                  scriptPkgs."codebase-memory-mcp"
                }/bin/codebase-memory-mcp config set auto_index_limit 50000
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
            ".local/bin/mcp-firecrawl" = {
              source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
              force = true;
            };
            ".local/bin/mcp-playwright" = {
              source = "${mcpPlaywrightBin}/bin/mcp-playwright";
              force = true;
            };
            ".local/bin/mcp-playwright-headed" = {
              source = "${mcpPlaywrightHeadedBin}/bin/mcp-playwright-headed";
              force = true;
            };
            ".local/bin/mcp-chrome-devtools" = {
              source = "${mcpChromeDevtoolsBin}/bin/mcp-chrome-devtools";
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
        };
    };
} args
