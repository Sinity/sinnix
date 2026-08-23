# Model Context Protocol (MCP) servers and AI-integrated tool settings: server
# wrappers, the lean/full/browser agent profiles, and Claude/Codex/Gemini
# dotfile integration.
#
# Domain pieces live in sibling plain-nix helpers, imported below:
# mcp-tools.nix (generic MCP wrappers), client-profiles.nix
# (registry-driven Codex/Gemini config), browser.nix, hooks.nix.
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
    antigravityMcpConfigSource = lib.mkOption {
      type = lib.types.path;
      internal = true;
      description = "Path to the generated Antigravity MCP configuration (for tests)";
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
      browser = import ./browser.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          inputs
          ;
        dotsRoot = config.sinnix.paths.dotsRoot;
      };
      mcpTools = import ./mcp-tools.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          config
          ;
      };
      clientProfiles = import ./client-profiles.nix {
        inherit
          lib
          pkgs
          inputs
          mcpRegistry
          tomlFormat
          jsonFormat
          ;
        dotsRoot = config.sinnix.paths.dotsRoot;
      };
      codexHooksFile = import ./hooks.nix {
        inherit pkgs;
        dotsRoot = config.sinnix.paths.dotsRoot;
      };
      inherit (browser)
        mcpChromeDevtoolsBin
        desktopControlScripts
        ;
      inherit (mcpTools)
        mcpFirecrawlBin
        mcpLynchpinText
        mcpPolylogueText
        ;
      inherit (clientProfiles)
        codexConfigFile
        codexModelsV1File
        codexExplorerAgentFile
        codexFullConfigFile
        codexLeanConfigFile
        codexEvidenceConfigFile
        codexBrowserConfigFile
        codexDeepseekConfigFile
        codexLocalConfigFile
        sharedSkillFarm
        codexSkillFarm
        geminiSettingsFile
        antigravityMcpConfigFile
        ;
    in
    lib.mkMerge [
      # NixOS-level systemd.user (manager="user", preserving the unit's
      # existing manager) rather than the previous home-manager.users.${user}
      # block: neither unit had a registered runtime surface either way, so
      # this is render-only aside from the namespace move and the gained
      # OnFailure path every generated job carries by default.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-settings-env-lint";
          description = "Audit project agent settings environment paths";
          surface = null;
        }
        {
          manager = "user";
          # A monthly read-only audit of project Claude settings. The two
          # Polylogue /tmp roots are intentional workstation-local paths. Keep
          # them explicit inputs so a new absolute path remains unexplained
          # and fails loud.
          execStart = "${pkgs.bash}/bin/bash -c 'install -d -m 0700 \"$XDG_STATE_HOME/sinnix/settings-env-lint\"; ${scriptPkgs.sinnix-settings-env-lint}/bin/sinnix-settings-env-lint --root /realm/project --intentional-prefix /tmp/polylogue-archive --intentional-prefix /tmp/polylogue-pytest > \"$XDG_STATE_HOME/sinnix/settings-env-lint/latest.json\"'";
          timer = {
            onCalendar = "*-*-01 04:20:00";
            persistent = true;
            accuracySec = "15min";
            description = "Monthly project agent settings environment audit";
          };
        }
      )
      {
        sinnix.features.dev.mcp-servers.codexConfigSource = codexConfigFile;
        sinnix.features.dev.mcp-servers.codexFullConfigSource = codexFullConfigFile;
        sinnix.features.dev.mcp-servers.codexLeanConfigSource = codexLeanConfigFile;
        sinnix.features.dev.mcp-servers.codexEvidenceConfigSource = codexEvidenceConfigFile;
        sinnix.features.dev.mcp-servers.codexBrowserConfigSource = codexBrowserConfigFile;
        sinnix.features.dev.mcp-servers.codexDeepseekConfigSource = codexDeepseekConfigFile;
        sinnix.features.dev.mcp-servers.codexLocalConfigSource = codexLocalConfigFile;
        sinnix.features.dev.mcp-servers.codexHooksSource = codexHooksFile;
        sinnix.features.dev.mcp-servers.antigravityMcpConfigSource = antigravityMcpConfigFile;
        sinnix.persistence.home.directories = [
          ".local/state/sinnix/settings-env-lint"
        ];

        home-manager.users.${user} =
          {
            pkgs,
            lib,
            config,
            secretPaths,
            mkDotsFileFor,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            # htoprc lives in dots/htop/htoprc (out-of-store symlink) instead of
            # `programs.htop.settings`, so edits take effect without a rebuild.
            # Safe only while no other module contributes to that option.
            programs.htop.enable = true;
            xdg.configFile."htop/htoprc".source = mkDotsFile "/htop/htoprc";

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
                  run mkdir -p "$HOME/.codex/agents"
                  run cp ${codexConfigFile} "$HOME/.codex/config.toml"
                  run cp ${codexModelsV1File} "$HOME/.codex/models-v1.json"
                  run cp ${codexExplorerAgentFile} "$HOME/.codex/agents/explorer.toml"
                  run cp ${codexFullConfigFile} "$HOME/.codex/full.config.toml"
                  run cp ${codexLeanConfigFile} "$HOME/.codex/lean.config.toml"
                  run cp ${codexEvidenceConfigFile} "$HOME/.codex/evidence.config.toml"
                  run cp ${codexBrowserConfigFile} "$HOME/.codex/browser.config.toml"
                  run cp ${codexDeepseekConfigFile} "$HOME/.codex/deepseek.config.toml"
                  run cp ${codexLocalConfigFile} "$HOME/.codex/local.config.toml"
                  run cp ${codexHooksFile} "$HOME/.codex/hooks.json"
                  run chmod 644 "$HOME/.codex/config.toml"
                  run chmod 644 "$HOME/.codex/models-v1.json"
                  run chmod 644 "$HOME/.codex/agents/explorer.toml"
                  run chmod 644 "$HOME/.codex/full.config.toml"
                  run chmod 644 "$HOME/.codex/lean.config.toml"
                  run chmod 644 "$HOME/.codex/evidence.config.toml"
                  run chmod 644 "$HOME/.codex/browser.config.toml"
                  run chmod 644 "$HOME/.codex/deepseek.config.toml"
                  run chmod 644 "$HOME/.codex/local.config.toml"
                  run chmod 644 "$HOME/.codex/hooks.json"
                '';
              };
            };

            home.file = {
              # One directory symlink, not per-file entries: a new agent
              # definition dropped into dots/claude/agents/ is live
              # immediately, no registration and no rebuild.
              ".config/claude/agents" = {
                source = mkDotsFile "/claude/agents";
                force = true;
              };
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
              ".gemini/config/mcp_config.json" = {
                source = antigravityMcpConfigFile;
                force = true;
              };
              ".gemini/config/skills" = {
                source = sharedSkillFarm;
                force = true;
              };
              ".gemini/config/AGENTS.md".source = mkDotsFile "/claude/CLAUDE.md";
              ".local/bin/mcp-firecrawl" = {
                source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
                force = true;
              };
              ".local/bin/mcp-chrome-devtools" = {
                source = "${mcpChromeDevtoolsBin}/bin/mcp-chrome-devtools";
                force = true;
              };
              ".local/bin/sinnix-chrome-control" = {
                source = config.lib.file.mkOutOfStoreSymlink "${desktopControlScripts}/chrome-control.sh";
                force = true;
              };
              ".local/bin/sinnix-hypr-control" = {
                source = config.lib.file.mkOutOfStoreSymlink "${desktopControlScripts}/hypr-control.sh";
                force = true;
              };
              ".local/bin/sinnix-keyboard-control" = {
                source = config.lib.file.mkOutOfStoreSymlink "${desktopControlScripts}/keyboard-control.sh";
                force = true;
              };
              ".local/bin/sinnix-kitty-control" = {
                source = config.lib.file.mkOutOfStoreSymlink "${desktopControlScripts}/kitty-remote-control.sh";
                force = true;
              };
              ".local/bin/sinnix-screenshot-control" = {
                source = config.lib.file.mkOutOfStoreSymlink "${desktopControlScripts}/screenshot-color-lab.sh";
                force = true;
              };
              ".local/bin/mcp-lynchpin" = {
                executable = true;
                force = true;
                text = mcpLynchpinText;
              };
              ".local/bin/mcp-polylogue" = {
                executable = true;
                force = true;
                text = mcpPolylogueText;
              };
              ".local/bin/mcp-sinex" = {
                source = "${scriptPkgs.sinnix-mcp-sinex}/bin/sinnix-mcp-sinex";
                force = true;
              };
              ".local/share/polylogue/inbox/chatgpt" = {
                source = config.lib.file.mkOutOfStoreSymlink "/realm/data/ai/chatlog/raw/chatgpt";
                force = true;
              };
              ".local/share/polylogue/inbox/claude" = {
                source = config.lib.file.mkOutOfStoreSymlink "/realm/data/ai/chatlog/raw/claude";
                force = true;
              };
            };
          };
      }
    ];
} args
