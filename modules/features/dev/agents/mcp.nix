# Model Context Protocol (MCP) servers and AI-integrated tool settings
#
# Provides:
# - MCP server wrappers (Firecrawl, Chrome DevTools, Polylogue, Lynchpin)
# - MCP server registry and explicit lean/full/browser agent profiles
# - Claude/Codex/Gemini dotfile linking and integration
# - System monitoring tools (htop)
#
# Domain pieces live in sibling plain-nix helpers, imported below:
# mcp-tools.nix (Firecrawl + Codebase Memory UI), client-profiles.nix
# (registry-driven Codex/Gemini config), serena.nix, browser.nix, hooks.nix.
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

      serena = import ./serena.nix { inherit lib pkgs scriptPkgs; };
      browser = import ./browser.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          inputs
          ;
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
      };
      codexHooksFile = import ./hooks.nix { inherit pkgs; };

      inherit (serena) serenaConfigFile mkSerenaWrapper;
      inherit (browser)
        mcpChromeDevtoolsBin
        mcpChromeDevtoolsPrivateBin
        mcpChromeDevtoolsPrivateVisibleBin
        desktopControlScripts
        ;
      inherit (mcpTools)
        mcpFirecrawlBin
        codebaseMemoryUiLauncher
        mcpLynchpinText
        mcpPolylogueText
        ;
      inherit (clientProfiles)
        codexConfigFile
        codexFullConfigFile
        codexLeanConfigFile
        codexEvidenceConfigFile
        codexBrowserConfigFile
        codexDeepseekConfigFile
        codexLocalConfigFile
        sharedSkillFarm
        codexSkillFarm
        geminiSettingsFile
        ;
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
          mkDotsFileFor,
          ...
        }:
        let
          mkDotsFile = mkDotsFileFor config;
        in
        {
          # htoprc lives in dots/htop/htoprc (live out-of-store symlink)
          # instead of `programs.htop.settings`: no other module touches
          # this option, so bypassing HM's settings-to-htoprc generator is
          # safe and edits take effect without a rebuild.
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
