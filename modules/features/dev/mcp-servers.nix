# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (PostgreSQL, Qdrant, Context7, etc.)
# - Claude/Codex/Gemini dotfile linking and integration
# - System monitoring tools (htop)
{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [ "dev" "mcp-servers" ];
  description = "MCP servers and AI tool integration";
  configFn =
    {
      config,
      lib,
      pkgs,
      inputs,
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      dotsRepoPath = config.sinnix.paths.dotsRoot;
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
      qdrantLdLibraryPath = lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
      ];
      mcpQdrantBin = pkgs.writeShellScriptBin "mcp-qdrant" ''
        set -euo pipefail
        export QDRANT_URL="''${QDRANT_URL:-http://127.0.0.1:6333}"
        if [ -n "''${LD_LIBRARY_PATH:-}" ]; then
          export LD_LIBRARY_PATH="${qdrantLdLibraryPath}:''${LD_LIBRARY_PATH}"
        else
          export LD_LIBRARY_PATH="${qdrantLdLibraryPath}"
        fi
        exec ${pkgs.uv}/bin/uv run 
          --with fastmcp 
          --with qdrant-client 
          -- python ${config.sinnix.paths.projectRoot}/scripts/mcp-qdrant.py
      '';
      mcpPostgresBin = pkgs.writeShellScriptBin "mcp-postgres" ''
        export POSTGRES_URL="postgresql://sinex:sinex@localhost:5432/sinex_dev"
        set -euo pipefail
        exec npx -y @modelcontextprotocol/server-postgres "$POSTGRES_URL"
      '';
      mcpSqliteBin = pkgs.writeShellScriptBin "mcp-sqlite" ''
        set -euo pipefail
        exec npx -y @modelcontextprotocol/server-sqlite "$@"
      '';
      mcpContext7Bin = pkgs.writeShellScriptBin "mcp-context7" ''
        set -euo pipefail
        exec npx -y @upstash/context7-mcp
      '';
      mcpFirecrawlBin = pkgs.writeShellScriptBin "mcp-firecrawl" ''
        set -euo pipefail
        ${firecrawlSecretExport}
        exec npx -y firecrawl-mcp
      '';
      mcpPlaywrightBin = pkgs.writeShellScriptBin "mcp-playwright" ''
        set -euo pipefail
        exec npx -y @playwright/mcp@latest
      '';
      mcpCclspBin = pkgs.writeShellScriptBin "mcp-cclsp" ''
        set -euo pipefail
        export CCLSP_CONFIG_PATH="''${CCLSP_CONFIG_PATH:-$HOME/.config/claude/cclsp.json}"
        exec npx -y cclsp@latest
      '';
    in
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          inputs,
          secretPaths,
          ...
        }:
        let
          mkDotsRepoLink = helpers.mkDotsSymlink config dotsRepoPath;
        in
        {
          programs.htop = {
            enable = true;
            settings = {
              detailed_cpu_time = true;
              hide_kernel_threads = false;
              hide_userland_threads = false;
              show_cpu_frequency = true;
              show_cpu_temperature = true;
              tree_view = true;
              sort_key = "PERCENT_CPU";
            };
          };

          home = {
            packages = [
              mcpQdrantBin
              mcpPostgresBin
              mcpSqliteBin
              mcpContext7Bin
              mcpFirecrawlBin
              mcpPlaywrightBin
              mcpCclspBin
            ];

            activation = {
              restoreConfigstore = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                if [ -f ${secretPaths."configstore-update-notifier"} ]; then
                  mkdir -p "$HOME/.config/configstore"
                  rm -rf "$HOME/.config/configstore/update-notifier-@google"
                  if ! ${pkgs.gzip}/bin/gzip -dc ${
                    secretPaths."configstore-update-notifier"
                  } | ${pkgs.gnutar}/bin/tar -xC "$HOME/.config/configstore"; then
                    echo "warning: unable to restore configstore notifier archive" >&2
                  fi
                fi
              '';
              prepareCodexSkills = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
                if [ -e "$HOME/.codex/skills" ] && [ ! -L "$HOME/.codex/skills" ]; then
                  rm -rf "$HOME/.codex/skills"
                fi
              '';
              linkPolylogueInbox = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                INBOX_DIR="$HOME/.local/share/polylogue/inbox"
                mkdir -p "$INBOX_DIR"
                if [ -d "/realm/data/exports/chatlog/raw/chatgpt" ]; then
                  ln -sfn "/realm/data/exports/chatlog/raw/chatgpt" "$INBOX_DIR/chatgpt"
                fi
                if [ -d "/realm/data/exports/chatlog/raw/claude" ]; then
                  ln -sfn "/realm/data/exports/chatlog/raw/claude" "$INBOX_DIR/claude"
                fi
              '';
            };
          };

          xdg.configFile = {
            "opencode/opencode.json".source = mkDotsRepoLink "/opencode/opencode.json";
            "sqlitebrowser/sqlitebrowser.conf".source = mkDotsRepoLink "/sqlitebrowser/sqlitebrowser.conf";
            "ripgrep-all/config.jsonc".source = mkDotsRepoLink "/ripgrep-all/config.jsonc";
            "marimo/marimo.toml".source = mkDotsRepoLink "/marimo/marimo.toml";
          };

          home.file = {
            ".codex/config.toml" = {
              source = mkDotsRepoLink "/codex/config.toml";
              force = true;
            };
            ".codex/skills" = {
              source = mkDotsRepoLink "/codex/skills";
              force = true;
              recursive = true;
            };
            ".local/bin/mcp-qdrant".source = "${mcpQdrantBin}/bin/mcp-qdrant";
            ".local/bin/mcp-postgres".source = "${mcpPostgresBin}/bin/mcp-postgres";
            ".local/bin/mcp-sqlite".source = "${mcpSqliteBin}/bin/mcp-sqlite";
            ".local/bin/mcp-context7".source = "${mcpContext7Bin}/bin/mcp-context7";
            ".local/bin/mcp-firecrawl".source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
            ".local/bin/mcp-playwright".source = "${mcpPlaywrightBin}/bin/mcp-playwright";
            ".local/bin/mcp-cclsp".source = "${mcpCclspBin}/bin/mcp-cclsp";
            ".gemini/settings.json" = {
              source = mkDotsRepoLink "/gemini/settings.json";
              force = true;
            };
          };
        };
    };
} args
