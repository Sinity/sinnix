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
      ".gemini/settings.json" = {
        source = "gemini/settings.json";
        force = true;
      };
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
      inherit (mcpRegistry)
        selectClientServers
        renderCodexServer
        ;
      codexMcpServers = lib.mapAttrs renderCodexServer (selectClientServers "codex");
      codexMcpConfigFile = tomlFormat.generate "codex-mcp.toml" { mcp_servers = codexMcpServers; };
      codexConfigFile = pkgs.runCommandLocal "codex-config.toml" { } ''
        cat ${inputs.self + "/dots/codex/config.toml"} ${codexMcpConfigFile} > "$out"
      '';
    in
    {
      sinnix.features.dev.mcp-servers.codexConfigSource = codexConfigFile;

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
            };
          };

          home.file = {
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
