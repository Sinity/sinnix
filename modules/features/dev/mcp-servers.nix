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
  extraOptions = { };
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
      mcpRegistry = import ../../lib/mcp-registry.nix { inherit lib; };
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
          runtimeSecretEnv ? { },
        }:
        pkgs.writeShellScriptBin name ''
          set -euo pipefail
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
      mcpPolylogueBin = mkMcpWrapper "mcp-polylogue" {
        command = "${scriptPkgs.polylogue-cli}/bin/polylogue-mcp";
      };
      geminiPkg = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.gemini-cli;
      inherit (mcpRegistry) selectClientServers renderForgeServer;
      forgeMcpServers = lib.mapAttrs renderForgeServer (selectClientServers "forge");
      forgeMcpConfigFile = jsonFormat.generate "forge-mcp.json" { mcpServers = forgeMcpServers; };
    in
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          mkDotsFileFor,
          secretPaths,
          ...
        }:
        let
          mkDotsFile = mkDotsFileFor config;
        in
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

          home.packages = [
            geminiPkg
          ];

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
            };
          };

          xdg.configFile = {
            "ripgrep-all/config.jsonc".source = mkDotsFile "/ripgrep-all/config.jsonc";
            "marimo/marimo.toml".source = mkDotsFile "/marimo/marimo.toml";
          };

          home.file = {
            # Canonical Codex location is ~/.codex.
            ".codex/config.toml" = {
              source = mkDotsFile "/codex/config.toml";
              force = true;
            };
            # Codex keeps a dedicated overlay tree; canonical shared skills live in dots/_ai/skills.
            ".codex/skills".source = mkDotsFile "/codex/skills";
            "forge/.mcp.json" = {
              source = forgeMcpConfigFile;
              force = true;
            };
            ".local/bin/mcp-firecrawl".source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
            ".local/bin/mcp-playwright".source = "${mcpPlaywrightBin}/bin/mcp-playwright";
            ".local/bin/mcp-polylogue".source = "${mcpPolylogueBin}/bin/mcp-polylogue";
            ".gemini/settings.json" = {
              source = mkDotsFile "/gemini/settings.json";
              force = true;
            };
            ".gemini/skills".source = mkDotsFile "/_ai/skills";
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
