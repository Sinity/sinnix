# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (PostgreSQL, Qdrant, Context7, etc.)
# - Claude/Codex/Gemini dotfile linking and integration
# - System monitoring tools (htop)
{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [
    "dev"
    "mcp-servers"
  ];
  description = "MCP servers and AI tool integration";
  configFn =
    {
      config,
      lib,
      pkgs,
      inputs,
      helpers,
      user,
      ...
    }:
    let
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
        set -euo pipefail
        # Prefer explicit overrides and project-provided DATABASE_URL (e.g. sinex xtask infra).
        if [ -n "''${POSTGRES_URL:-}" ]; then
          db_url="$POSTGRES_URL"
        elif [ -n "''${DATABASE_URL:-}" ]; then
          db_url="$DATABASE_URL"
        elif [ -n "''${SINEX_DEV_STATE_DIR:-}" ]; then
          db_url="postgresql:///sinex_dev?host=''${SINEX_DEV_STATE_DIR}/run&port=''${SINEX_DEV_PG_PORT:-5432}&user=''${USER:-sinity}"
        elif [ -n "''${PGHOST:-}" ]; then
          db_url="postgresql:///''${PGDATABASE:-sinex_dev}?host=''${PGHOST}&port=''${PGPORT:-5432}&user=''${PGUSER:-''${USER:-sinity}}"
        else
          db_url="postgresql://sinex:sinex@localhost:5432/sinex_dev"
        fi
        exec npx -y @modelcontextprotocol/server-postgres "$db_url"
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
        if [ -z "''${CCLSP_CONFIG_PATH:-}" ]; then
          if [ -f "$PWD/.cclsp.json" ]; then
            export CCLSP_CONFIG_PATH="$PWD/.cclsp.json"
          else
            export CCLSP_CONFIG_PATH="$HOME/.config/claude/cclsp.json"
          fi
        fi
        exec npx -y cclsp@latest
      '';
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
              hide_kernel_threads = false;
              hide_userland_threads = false;
              show_cpu_frequency = true;
              show_cpu_temperature = true;
              tree_view = true;
              sort_key = "PERCENT_CPU";
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
            "opencode/opencode.json".source = mkDotsFile "/opencode/opencode.json";
            "sqlitebrowser/sqlitebrowser.conf".source = mkDotsFile "/sqlitebrowser/sqlitebrowser.conf";
            "ripgrep-all/config.jsonc".source = mkDotsFile "/ripgrep-all/config.jsonc";
            "marimo/marimo.toml".source = mkDotsFile "/marimo/marimo.toml";
          };

          home.file = {
            ".codex/config.toml" = {
              source = mkDotsFile "/codex/config.toml";
              force = true;
            };
            ".codex/skills" = {
              source = mkDotsFile "/codex/skills";
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
              source = mkDotsFile "/gemini/settings.json";
              force = true;
            };
          };
        };
    };
} args
