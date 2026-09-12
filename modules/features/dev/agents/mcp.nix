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
      # The Home Manager user function below also calls its argument `config`.
      # Keep the NixOS-level live dots root in this lexical binding so nested
      # activation text cannot accidentally resolve the Home Manager config.
      dotsRoot = config.sinnix.paths.dotsRoot;
      inherit (helpers.data) mcpRegistry agentLanes;
      browser = import ./browser.nix {
        inherit
          lib
          pkgs
          scriptPkgs
          inputs
          ;
        inherit dotsRoot;
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
          agentLanes
          tomlFormat
          jsonFormat
          ;
        inherit dotsRoot;
      };
      codexHooksFile = import ./hooks.nix {
        inherit pkgs;
        inherit dotsRoot;
      };
      codexMigrationPython = pkgs.python3.withPackages (ps: [ ps.tomlkit ]);
      # This is the old copied-to-private baseline, not the live system
      # default. Keep it immutable so a later dots edit cannot alter the
      # one-time three-way migration, and so activation does not depend on a
      # checkout being mounted (as in the hermetic runtime fixture).
      codexSystemDefaultsBaseline = pkgs.writeText "sinnix-codex-system-defaults-v1.toml" (
        builtins.readFile "${inputs.self}/dots/codex/config.toml"
      );
      codexSystemDefaultsMigration = pkgs.writeText "sinnix-codex-system-defaults-migration.py" ''
        import os
        import sys
        from pathlib import Path

        import tomlkit

        baseline_path, user_path = map(Path, sys.argv[1:])
        baseline = tomlkit.parse(baseline_path.read_text())
        user = tomlkit.parse(user_path.read_text())

        def values_match(left, right):
            unwrap_left = left.unwrap() if hasattr(left, "unwrap") else left
            unwrap_right = right.unwrap() if hasattr(right, "unwrap") else right
            return unwrap_left == unwrap_right

        def retain_user_overlay(old, current):
            for key in list(current):
                if key not in old:
                    continue
                old_value = old[key]
                current_value = current[key]
                if hasattr(old_value, "items") and hasattr(current_value, "items"):
                    retain_user_overlay(old_value, current_value)
                    if not list(current_value):
                        del current[key]
                elif values_match(old_value, current_value):
                    del current[key]

        retain_user_overlay(baseline, user)
        temporary = user_path.with_name(user_path.name + ".sinnix-migration.tmp")
        temporary.write_text(tomlkit.dumps(user))
        os.chmod(temporary, 0o600)
        os.replace(temporary, user_path)
      '';
      # Codex persists profile-scoped state, including hook trust, in the
      # selected <profile>.config.toml.  Profile MCP servers remain declarative,
      # but the file itself must be a private writable overlay rather than a
      # Home Manager link into the store.
      codexNativeProfileMigration = pkgs.writeText "sinnix-codex-native-profile-migration.py" ''
        import os
        import stat
        import sys
        import tempfile
        from pathlib import Path

        import tomlkit

        source_path, profile_path, backup_path = map(Path, sys.argv[1:])
        generated = tomlkit.parse(source_path.read_text())

        def merge_overlay(destination, overlay, root=True):
            for key, value in overlay.items():
                # The MCP registry is the sole owner of the profile server
                # table. All other app-owned settings, especially hooks.state,
                # remain private and writable.
                if root and key == "mcp_servers":
                    continue
                if (
                    key in destination
                    and hasattr(destination[key], "items")
                    and hasattr(value, "items")
                ):
                    merge_overlay(destination[key], value, root=False)
                else:
                    destination[key] = value

        def values_match(left, right):
            unwrap_left = left.unwrap() if hasattr(left, "unwrap") else left
            unwrap_right = right.unwrap() if hasattr(right, "unwrap") else right
            return unwrap_left == unwrap_right

        def retain_user_overlay(baseline, overlay):
            for key in list(overlay):
                if key not in baseline:
                    continue
                old_value = baseline[key]
                overlay_value = overlay[key]
                if hasattr(old_value, "items") and hasattr(overlay_value, "items"):
                    retain_user_overlay(old_value, overlay_value)
                    if not list(overlay_value):
                        del overlay[key]
                elif values_match(old_value, overlay_value):
                    del overlay[key]

        if profile_path.is_symlink():
            if not str(profile_path.resolve(strict=False)).startswith("/nix/store/"):
                raise RuntimeError(
                    f"refusing to replace an unrecognised Codex profile link: {profile_path}"
                )
            # Native layers were previously store links. Their only writable
            # state was saved beside the migration marker before the link was
            # installed, so recover that state instead of treating the linked
            # generated file as a user overlay.
            overlay_paths = []
            if backup_path.is_file():
                legacy_overlay = tomlkit.parse(backup_path.read_text())
                try:
                    # The link still names the old generated layer. Compare
                    # against it so an old generated default is not revived as
                    # private state when the new layer is rendered.
                    retain_user_overlay(
                        tomlkit.parse(profile_path.read_text()),
                        legacy_overlay,
                    )
                except OSError:
                    print(
                        f"codex: could not compare legacy profile backup for {profile_path}; preserving its non-MCP settings",
                        file=sys.stderr,
                    )
                overlay_paths = [ legacy_overlay ]
            current_text = None
        elif profile_path.is_file():
            overlay_paths = [ profile_path ]
            current_text = profile_path.read_text()
        elif profile_path.exists():
            raise RuntimeError(f"Codex profile path is not a file: {profile_path}")
        else:
            overlay_paths = [ backup_path ] if backup_path.is_file() else []
            current_text = None

        for overlay in overlay_paths:
            if isinstance(overlay, Path):
                overlay = tomlkit.parse(overlay.read_text())
            merge_overlay(generated, overlay)

        rendered = tomlkit.dumps(generated)
        mode = (
            stat.S_IMODE(profile_path.stat().st_mode)
            if profile_path.is_file() and not profile_path.is_symlink()
            else None
        )
        if current_text == rendered and mode == 0o600:
            sys.exit(0)

        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{profile_path.name}.",
            suffix=".tmp",
            dir=profile_path.parent,
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                temporary_file.write(rendered)
            os.replace(temporary, profile_path)
        except BaseException:
            os.unlink(temporary)
            raise
      '';
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
        codexProfileFiles
        codexEndpointFiles
        geminiSettingsFile
        antigravityMcpConfigFile
        ;
      codexConfigFiles = codexProfileFiles // codexEndpointFiles;
      codexFullConfigFile = codexProfileFiles.full;
      codexLeanConfigFile = codexProfileFiles.lean;
      codexEvidenceConfigFile = codexProfileFiles.evidence;
      codexBrowserConfigFile = codexProfileFiles.browser;
      codexDeepseekConfigFile = codexEndpointFiles.deepseek;
      codexLocalConfigFile = codexEndpointFiles.local;
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
        # Codex reads this live system layer before its private overlay.
        environment.etc."codex/config.toml".source = "${dotsRoot}/codex/config.toml";
        environment.etc."codex/agents/explorer.toml".source = "${dotsRoot}/codex/agents/explorer.toml";
        sinnix.features.dev.mcp-servers.codexConfigSource = inputs.self + "/dots/codex/config.toml";
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
                # Prior generations copied managed values into the private
                # config. Remove only values unchanged from that old baseline;
                # retain user changes and unknown keys as the private overlay.
                codexSystemDefaultsMigration = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
                  codex_home="$HOME/.codex"
                  codex_config="$codex_home/config.toml"
                  codex_marker="$codex_home/.sinnix-system-defaults-v1"
                  codex_pending="$codex_marker.pending"
                  codex_baseline=${lib.escapeShellArg (toString codexSystemDefaultsBaseline)}
                  run mkdir -p "$codex_home"
                  if [ ! -e "$codex_marker" ]; then
                    if [ -e "$codex_pending" ]; then
                      echo "codex: system-default migration is pending; preserving private config for review" >&2
                    elif [ -f "$codex_config" ]; then
                      if [ ! -e "$codex_config.sinnix-before-system-defaults-v1.bak" ]; then
                        run cp -p "$codex_config" "$codex_config.sinnix-before-system-defaults-v1.bak"
                        run chmod 600 "$codex_config.sinnix-before-system-defaults-v1.bak"
                      fi
                      run touch "$codex_pending"
                      if run ${codexMigrationPython}/bin/python ${codexSystemDefaultsMigration} "$codex_baseline" "$codex_config"; then
                        run mv "$codex_pending" "$codex_marker"
                      else
                        run rm "$codex_pending"
                        echo "codex: retained an unreadable private config; migration will retry after it is repaired" >&2
                      fi
                    else
                      run touch "$codex_marker"
                    fi
                  fi
                '';
                # hooks.json is still a Home Manager link. Preserve a
                # differing legacy copy before linkGeneration replaces it.
                codexHooksBackup = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
                  codex_home="$HOME/.codex"
                  codex_backup="$codex_home/.sinnix-before-native-layers-v1"
                  codex_marker="$codex_backup/.complete"
                  if [ ! -e "$codex_marker" ]; then
                    run mkdir -p "$codex_backup"
                    codex_source=${lib.escapeShellArg (toString codexHooksFile)}
                    codex_destination="$codex_home/hooks.json"
                    if [ -f "$codex_destination" ] || [ -L "$codex_destination" ]; then
                      if ! cmp -s "$codex_destination" "$codex_source" && [ ! -e "$codex_backup/hooks.json" ] && [ ! -L "$codex_backup/hooks.json" ]; then
                        run cp -a "$codex_destination" "$codex_backup/hooks.json"
                      fi
                    fi
                    run touch "$codex_marker"
                  fi
                '';
                codexNativeProfiles = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
                  codex_home="$HOME/.codex"
                  codex_backup="$codex_home/.sinnix-before-native-layers-v1"
                  run mkdir -p "$codex_home"
                  ${lib.concatMapStringsSep "\n" (codex_name: ''
                    run ${codexMigrationPython}/bin/python ${codexNativeProfileMigration} \
                      ${lib.escapeShellArg (toString codexConfigFiles.${codex_name})} \
                      "$codex_home/${codex_name}.config.toml" \
                      "$codex_backup/${codex_name}.config.toml"
                  '') (lib.attrNames codexConfigFiles)}
                '';
                # ~/.codex/skills can contain app-installed skills and Codex's
                # .system directory. Expand only a recognisable old Sinnix
                # farm. An unknown directory symlink is ambiguous user state
                # and is deliberately left untouched.
                codexSkills = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
                  codex_skills="$HOME/.codex/skills"
                  declared_skills="${dotsRoot}/codex/skills"
                  codex_manage_skills=1
                  if [ -L "$codex_skills" ]; then
                    codex_link="$(readlink "$codex_skills" || true)"
                    codex_old="$(readlink -f "$codex_skills" || true)"
                    codex_owned_farm=1
                    codex_system_link=""
                    # Only the old Home Manager output that wrapped our named
                    # codex farm is safe to replace. A custom or empty link is
                    # still private state, even if it happens to look sparse.
                    case "$codex_link:$codex_old" in
                      /nix/store/*-home-manager-files/.codex/skills:/nix/store/*-sinnix-codex-agent-skills) ;;
                      *) codex_owned_farm=0 ;;
                    esac
                    if [ -z "$codex_old" ] || [ ! -d "$codex_old" ] || [ ! -L "$codex_old/.system" ]; then
                      codex_owned_farm=0
                    else
                      for codex_entry in "$codex_old"/* "$codex_old"/.[!.]*; do
                        [ -e "$codex_entry" ] || [ -L "$codex_entry" ] || continue
                        codex_name="$(basename "$codex_entry")"
                        if [ "$codex_name" = .system ]; then
                          codex_system_link="$(readlink "$codex_entry" || true)"
                          continue
                        fi
                        codex_target="$(readlink -f "$codex_entry" || true)"
                        if [ "$codex_target" != "${dotsRoot}/_ai/skills/$codex_name" ] && [ "$codex_target" != "$(readlink -f "$declared_skills/$codex_name" || true)" ]; then
                          codex_owned_farm=0
                          break
                        fi
                      done
                    fi
                    if [ "$codex_owned_farm" -eq 1 ]; then
                      run rm "$codex_skills"
                      run mkdir -p "$codex_skills"
                      if [ -n "$codex_system_link" ]; then
                        run ln -s "$codex_system_link" "$codex_skills/.system"
                      fi
                    else
                      echo "codex: preserving an unrecognised ~/.codex/skills link" >&2
                      codex_manage_skills=0
                    fi
                  else
                    run mkdir -p "$codex_skills"
                  fi
                  if [ "$codex_manage_skills" -eq 1 ]; then
                  for codex_entry in "$codex_skills"/* "$codex_skills"/.[!.]*; do
                    [ -L "$codex_entry" ] || continue
                    codex_name="$(basename "$codex_entry")"
                    codex_target="$(readlink -f "$codex_entry" || true)"
                    if [ "$codex_target" = "${dotsRoot}/_ai/skills/$codex_name" ] && [ ! -e "$declared_skills/$codex_name" ]; then
                      run rm "$codex_entry"
                    fi
                  done
                  for codex_source in "$declared_skills"/* "$declared_skills"/.[!.]*; do
                    [ -e "$codex_source" ] || [ -L "$codex_source" ] || continue
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
              ".agents/skills" = {
                source = mkDotsFile "/_ai/skills";
                force = true;
              };
              ".codex/agents/explorer.toml" = {
                source = mkDotsFile "/codex/agents/explorer.toml";
                force = true;
              };
              ".codex/hooks.json" = {
                source = codexHooksFile;
                force = true;
              };
              ".gemini/skills" = {
                source = mkDotsFile "/_ai/skills";
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
                source = mkDotsFile "/_ai/skills";
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
            };
          };
      }
    ];
} args
