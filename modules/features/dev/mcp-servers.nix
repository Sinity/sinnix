# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (Context7, Firecrawl, Playwright)
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
    context7Singleton = lib.mkOption {
      type = lib.types.submodule {
        options = {
          enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Run Context7 MCP as a singleton HTTP service for all MCP clients.";
          };
          port = lib.mkOption {
            type = lib.types.ints.between 1 65535;
            default = 3939;
            description = "Local port for the Context7 singleton MCP service.";
          };
        };
      };
      default = { };
      description = "Context7 singleton service settings.";
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
      firecrawlSecretPath = lib.attrByPath [ "sinnix" "secrets" "paths" "firecrawl-api-key" ] null config;
      firecrawlSecretExport =
        if firecrawlSecretPath != null then
          ''
            if [ -z "''${FIRECRAWL_API_KEY:-}" ] && [ -r ${firecrawlSecretPath} ]; then
              export FIRECRAWL_API_KEY="$(<${firecrawlSecretPath})"
            fi
          ''
        else
          "";
      mcpContext7Pkg = scriptPkgs.mcp-context7;
      mcpFirecrawlPkg = scriptPkgs.mcp-firecrawl;
      mcpContext7Bin = pkgs.writeShellScriptBin "mcp-context7" ''
        set -euo pipefail
        exec ${mcpContext7Pkg}/bin/mcp-context7 "$@"
      '';
      mcpFirecrawlBin = pkgs.writeShellScriptBin "mcp-firecrawl" ''
        set -euo pipefail
        ${firecrawlSecretExport}
        exec ${mcpFirecrawlPkg}/bin/mcp-firecrawl "$@"
      '';
      mcpPlaywrightBin = pkgs.writeShellScriptBin "mcp-playwright" ''
        set -euo pipefail
        exec ${pkgs.playwright-mcp}/bin/playwright-mcp "$@"
      '';
      mcpPolylogueBin = pkgs.writeShellScriptBin "mcp-polylogue" ''
        set -euo pipefail
        exec ${scriptPkgs.polylogue-cli}/bin/polylogue mcp "$@"
      '';
      geminiPkg = inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system}.gemini-cli;
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

          systemd.user.services.mcp-context7-singleton = lib.mkIf cfg.context7Singleton.enable {
            Unit = {
              Description = "Context7 MCP singleton (HTTP)";
              After = [ "network-online.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${mcpContext7Bin}/bin/mcp-context7 --transport http --port ${toString cfg.context7Singleton.port}";
              Restart = "on-failure";
              RestartSec = "2s";
            };
            Install.WantedBy = [ "default.target" ];
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
            ".codex/skills" = {
              source = mkDotsFile "/codex/skills";
              force = true;
              recursive = true;
            };
            ".local/bin/mcp-context7".source = "${mcpContext7Bin}/bin/mcp-context7";
            ".local/bin/mcp-firecrawl".source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
            ".local/bin/mcp-playwright".source = "${mcpPlaywrightBin}/bin/mcp-playwright";
            ".local/bin/mcp-polylogue".source = "${mcpPolylogueBin}/bin/mcp-polylogue";
            ".gemini/settings.json" = {
              source = mkDotsFile "/gemini/settings.json";
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
        };
    };
} args
