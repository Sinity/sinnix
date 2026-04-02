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
      jsonFormat = pkgs.formats.json { };
      tomlFormat = pkgs.formats.toml { };
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
      mcpContext7Bin = mkMcpWrapper "mcp-context7" {
        command = "${scriptPkgs.mcp-context7}/bin/mcp-context7";
      };
      mcpFirecrawlBin = mkMcpWrapper "mcp-firecrawl" {
        command = "${scriptPkgs.mcp-firecrawl}/bin/mcp-firecrawl";
        runtimeSecretEnv = lib.optionalAttrs (firecrawlSecretPath != null) {
          FIRECRAWL_API_KEY = firecrawlSecretPath;
        };
      };
      mcpPlaywrightBin = mkMcpWrapper "mcp-playwright" {
        command = "${pkgs.playwright-mcp}/bin/mcp-server-playwright";
      };
      mcpPolylogueBin = mkMcpWrapper "mcp-polylogue" {
        command = "${scriptPkgs.polylogue-cli}/bin/polylogue";
        args = [ "mcp" ];
      };
      geminiPkg = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.gemini-cli;
      pruneAttrs = lib.filterAttrs (_: value: value != null && value != [ ] && value != { });
      mcpServerRegistry =
        (lib.optionalAttrs cfg.context7Singleton.enable {
          context7 = {
            transport = "http";
            url = "http://127.0.0.1:${toString cfg.context7Singleton.port}/mcp";
            clients = [
              "codex"
              "gemini"
              "forge"
            ];
          };
        })
        // {
          github = {
            transport = "http";
            url = "https://api.githubcopilot.com/mcp/";
            clients = [
              "codex"
              "gemini"
            ];
            codex = {
              bearer_token_env_var = "GITHUB_TOKEN";
            };
            gemini = {
              headers = {
                Authorization = "Bearer \${GITHUB_TOKEN}";
              };
            };
          };
          firecrawl = {
            transport = "stdio";
            command = "mcp-firecrawl";
            clients = [ "forge" ];
          };
          polylogue = {
            transport = "stdio";
            command = "mcp-polylogue";
            clients = [
              "codex"
              "claude"
              "gemini"
              "forge"
            ];
          };
          playwright = {
            transport = "stdio";
            command = "mcp-playwright";
            args = [ "--headless" ];
            clients = [ "forge" ];
          };
        };
      selectClientServers =
        client: lib.filterAttrs (_: server: builtins.elem client server.clients) mcpServerRegistry;
      renderCodexServer =
        _name: server:
        if server.transport == "http" then
          pruneAttrs (
            {
              inherit (server) url;
            }
            // (server.codex or { })
          )
        else
          pruneAttrs {
            inherit (server) command;
            args = server.args or [ ];
          };
      renderClaudeServer =
        _name: server:
        pruneAttrs {
          inherit (server) command;
          args = server.args or [ ];
        };
      renderGeminiServer =
        _name: server:
        if server.transport == "http" then
          pruneAttrs (
            {
              httpUrl = server.url;
            }
            // (server.gemini or { })
          )
        else
          pruneAttrs {
            inherit (server) command;
            args = server.args or [ ];
          };
      renderForgeServer =
        _name: server:
        pruneAttrs (
          if server.transport == "http" then
            {
              url = server.url;
              disable = false;
            }
          else
            {
              inherit (server) command;
              args = server.args or [ ];
              disable = false;
            }
        );
      codexMcpServers = lib.mapAttrs renderCodexServer (selectClientServers "codex");
      claudeMcpServers = lib.mapAttrs renderClaudeServer (selectClientServers "claude");
      geminiMcpServers = lib.mapAttrs renderGeminiServer (selectClientServers "gemini");
      forgeMcpServers = lib.mapAttrs renderForgeServer (selectClientServers "forge");
      generatedCodexConfig = (builtins.fromTOML (builtins.readFile ../../../dots/codex/config.toml)) // {
        mcp_servers = codexMcpServers;
      };
      generatedClaudeSettings =
        (builtins.fromJSON (builtins.readFile ../../../dots/claude/settings.json))
        // {
          mcpServers = claudeMcpServers;
        };
      generatedGeminiSettings =
        (builtins.fromJSON (builtins.readFile ../../../dots/gemini/settings.json))
        // {
          mcpServers = geminiMcpServers;
        };
      codexConfigFile = tomlFormat.generate "codex-config.toml" generatedCodexConfig;
      claudeSettingsFile = jsonFormat.generate "claude-settings.json" generatedClaudeSettings;
      geminiSettingsFile = jsonFormat.generate "gemini-settings.json" generatedGeminiSettings;
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
            "claude/settings.json".source = lib.mkForce claudeSettingsFile;
            "ripgrep-all/config.jsonc".source = mkDotsFile "/ripgrep-all/config.jsonc";
            "marimo/marimo.toml".source = mkDotsFile "/marimo/marimo.toml";
          };

          home.file = {
            # Canonical Codex location is ~/.codex.
            ".codex/config.toml" = {
              source = codexConfigFile;
              force = true;
            };
            # Codex keeps a dedicated overlay tree; canonical shared skills live in dots/_ai/skills.
            ".codex/skills" = {
              source = mkDotsFile "/codex/skills";
              force = true;
              recursive = true;
            };
            "forge/.mcp.json" = {
              source = forgeMcpConfigFile;
              force = true;
            };
            ".local/bin/mcp-context7".source = "${mcpContext7Bin}/bin/mcp-context7";
            ".local/bin/mcp-firecrawl".source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
            ".local/bin/mcp-playwright".source = "${mcpPlaywrightBin}/bin/mcp-playwright";
            ".local/bin/mcp-polylogue".source = "${mcpPolylogueBin}/bin/mcp-polylogue";
            ".gemini/settings.json" = {
              source = geminiSettingsFile;
              force = true;
            };
            ".gemini/skills" = {
              source = mkDotsFile "/_ai/skills";
              force = true;
              recursive = true;
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
