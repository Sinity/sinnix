# Model Context Protocol (MCP) servers and AI-integrated tool settings: server
# wrappers and default Claude/Codex integration.
#
# Domain pieces live in sibling plain-nix helpers, imported below:
# mcp-tools.nix (generic MCP wrappers), client-profiles.nix
# (registry-driven Codex config), hooks.nix.
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
      tomlFormat = pkgs.formats.toml { };
      # The Home Manager user function below also calls its argument `config`.
      # Keep the NixOS-level live dots root in this lexical binding so nested
      # activation text cannot accidentally resolve the Home Manager config.
      dotsRoot = config.sinnix.paths.dotsRoot;
      inherit (helpers.data) mcpRegistry;
      # Codex agent roles: one file per role under dots/codex/agents, named by
      # an [agents.<role>] table in dots/codex/config.toml. Each is linked
      # live beside the system config, which resolves `config_file` relative
      # to itself, and into the Codex home.
      codexAgentRoles = [
        "explorer"
        "implementer"
        "review"
      ];
      codexAgentRoleFile = role: "codex/agents/${role}.toml";
      # Browser control goes through sinnix-chrome-control, which attaches
      # to the operator's running Chrome and opens its own agent window.
      # Live dots path, not `inputs.self + ...`: a store copy would mean a
      # rebuild before any edit to these control scripts could be exercised.
      # Consumers reference it via mkOutOfStoreSymlink rather than string
      # interpolation, or Nix copies the directory into the store.
      desktopControlScripts = dotsRoot + "/_ai/skills/desktop-control/scripts";
      mcpTools = import ./mcp-tools.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          config
          inputs
          ;
      };
      clientProfiles = import ./client-profiles.nix {
        inherit
          lib
          inputs
          mcpRegistry
          tomlFormat
          ;
      };
      codexHooksFile = import ./hooks.nix {
        inherit pkgs;
        inherit dotsRoot;
      };
      inherit (mcpTools)
        mcpFirecrawlBin
        mcpLynchpinText
        mcpPolylogueText
        mcpSinexText
        ;
      inherit (clientProfiles) codexSystemConfigFile;
    in
    lib.mkMerge [
      {
        # Codex reads this live system layer before its private overlay.
        environment.etc = {
          "codex/config.toml".source = codexSystemConfigFile;
          # Hooks sit beside the system config, not in the Codex home: Codex
          # runs a system layer's hooks as managed policy, while a hook in
          # ~/.codex/hooks.json is skipped until the operator trusts its
          # exact definition in `/hooks`, again after every change.
          "codex/hooks.json".source = codexHooksFile;
        }
        // lib.genAttrs (map codexAgentRoleFile codexAgentRoles) (file: {
          source = "${dotsRoot}/${file}";
        });
        sinnix.features.dev.mcp-servers.codexConfigSource = codexSystemConfigFile;
        sinnix.features.dev.mcp-servers.codexHooksSource = codexHooksFile;

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
                # Codex's private config wins over the generated one, and
                # programs other than Sinnix write tool servers into it. A
                # private table that gives a registry server another command
                # is removed; the script's header has the rule.
                codexPrivateServers = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                  run ${pkgs.python3}/bin/python3 ${./codex-private-servers.py} \
                    "$HOME/.codex/config.toml" ${codexSystemConfigFile}
                '';
                # ~/.codex/skills also holds app-installed skills and Codex's
                # .system directory, so each declared skill gets its own link.
                # A ~/.codex/skills that is itself a symlink is private state
                # and is left untouched.
                codexSkills = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
                  codex_skills="$HOME/.codex/skills"
                  declared_skills="${dotsRoot}/_ai/skills"
                  if [ -L "$codex_skills" ]; then
                    echo "codex: preserving an unrecognised ~/.codex/skills link" >&2
                  else
                    run mkdir -p "$codex_skills"
                    for codex_entry in "$codex_skills"/* "$codex_skills"/.[!.]*; do
                      [ -L "$codex_entry" ] || continue
                      codex_name="$(basename "$codex_entry")"
                      codex_target="$(readlink -m "$codex_entry" || true)"
                      # A declared entry without SKILL.md (a retired skill, the
                      # harness-owned synced/ and .trash/ trees) is not a skill.
                      if [ "$codex_target" = "$declared_skills/$codex_name" ] && [ ! -e "$declared_skills/$codex_name/SKILL.md" ]; then
                        run rm "$codex_entry"
                      fi
                    done
                    for codex_source in "$declared_skills"/*; do
                      [ -e "$codex_source/SKILL.md" ] || continue
                      codex_name="$(basename "$codex_source")"
                      codex_destination="$codex_skills/$codex_name"
                      if [ -e "$codex_destination" ] || [ -L "$codex_destination" ]; then
                        codex_target="$(readlink -f "$codex_destination" || true)"
                        if [ "$codex_target" != "$(readlink -f "$codex_source")" ]; then
                          echo "codex: preserving existing skill $codex_name" >&2
                          continue
                        fi
                        run rm "$codex_destination"
                      fi
                      run ln -s "$codex_source" "$codex_destination"
                    done
                  fi
                '';
                directMutableAgentLinks = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
                  direct_link() {
                    target="$1"
                    source="$2"
                    if [ -e "$target" ] || [ -L "$target" ]; then
                      current="$(readlink -f "$target" 2>/dev/null || true)"
                      expected="$(readlink -f "$source")"
                      if [ "$current" != "$expected" ]; then
                        echo "sinnix: preserving unrecognised mutable agent file $target" >&2
                        return
                      fi
                      run rm "$target"
                    fi
                    run mkdir -p "$(dirname "$target")"
                    run ln -s "$source" "$target"
                  }
                  direct_link "$HOME/.config/claude/CLAUDE.md" "${dotsRoot}/_ai/AGENTS.md"
                  direct_link "$HOME/.config/claude/agents" "${dotsRoot}/claude/agents"
                  direct_link "$HOME/.config/claude/skills" "${dotsRoot}/_ai/skills"
                  direct_link "$HOME/.agents/skills" "${dotsRoot}/_ai/skills"
                  ${lib.concatMapStringsSep "\n" (
                    role: ''direct_link "$HOME/.${codexAgentRoleFile role}" "${dotsRoot}/${codexAgentRoleFile role}"''
                  ) codexAgentRoles}
                '';
              };
            };

            home.file =
              lib.genAttrs (map (role: ".${codexAgentRoleFile role}") codexAgentRoles) (file: {
                source = mkDotsFile "/${lib.removePrefix "." file}";
                force = true;
              })
              // {
                ".config/claude/agents" = {
                  source = mkDotsFile "/claude/agents";
                  force = true;
                };
                ".agents/skills" = {
                  source = mkDotsFile "/_ai/skills";
                  force = true;
                };
                ".local/bin/mcp-github" = {
                  source = "${scriptPkgs.mcp-github}/bin/mcp-github";
                  force = true;
                };
                ".local/bin/mcp-firecrawl" = {
                  source = "${mcpFirecrawlBin}/bin/mcp-firecrawl";
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
                  executable = true;
                  text = mcpSinexText;
                  force = true;
                };
              };
          };
      }
    ];
} args
