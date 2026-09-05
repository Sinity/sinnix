# Contract for the GUI file-navigation route: manager, preview helpers,
# declarative places, portal file selection, and MIME ownership.
# Decisions and measurements: docs/desktop-file-navigation.md
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        hmFor
        mkHmRuntimeCheck
        mkRuntimeCheck
        mountTmpfsRoots
        ;

      fixtures = ../tests/fixtures/desktop-file-navigation;

      # Content types the manager cannot render itself: each one must be
      # claimed by a declared preview helper.
      previewCases = [
        {
          mime = "video/mp4";
          fixture = "sample.mp4";
        }
        {
          mime = "application/pdf";
          fixture = "sample.pdf";
        }
      ];

      # Desktop entries that would otherwise win the types mime.nix declares:
      # kitty claims inode/directory, and the PDF preview helper claims
      # application/pdf.
      competingHandlers = [
        pkgs.kitty
        pkgs.qutebrowser
      ];

      # One type per family mime.nix owns; each must stay explicitly declared
      # rather than resolving through installed desktop entries.
      representativeHandlers = [
        {
          mime = "text/plain";
          handler = "sinnix-text-preview.desktop";
        }
        {
          mime = "text/html";
          handler = "google-chrome.desktop";
        }
        {
          mime = "application/pdf";
          handler = "org.qutebrowser.qutebrowser.desktop";
        }
        {
          mime = "image/png";
          handler = "imv.desktop";
        }
        {
          mime = "video/mp4";
          handler = "mpv.desktop";
        }
      ];

      navOf = config: config.sinnix.features.desktop.common-apps.fileNavigation;

      spec = {
        name = "desktop-file-navigation";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          (_: {
            networking.hostName = "desktop-file-navigation";
            sinnix.machine.isDesktop = true;
          })
        ];
        assertions =
          config:
          let
            hm = hmFor config;
            nav = navOf config;
            portalDirUnits = lib.filterAttrs (
              _: unit: (unit.environment or { }) ? XDG_DESKTOP_PORTAL_DIR
            ) config.systemd.user.services;
            expectedBookmarks = map (place: "file://${place.path} ${place.name}") nav.places;
            declaredRoots = [
              config.sinnix.paths.realmRoot
              config.sinnix.paths.neoOuterRealm
              config.sinnix.paths.outerRealm
            ];
            fromDeclaredRoot = path: builtins.any (root: lib.hasPrefix "${root}/" path) declaredRoots;
            hyprlandPortalConf = config.environment.etc."xdg/xdg-desktop-portal/hyprland-portals.conf".text;
          in
          [
            {
              assertion = builtins.elem nav.manager hm.home.packages;
              message = "The declared file manager is not installed in the Home Manager profile.";
            }
            {
              assertion = builtins.all (helper: builtins.elem helper hm.home.packages) nav.previewHelpers;
              message = "A declared preview helper is missing from the Home Manager profile; its content type would lose previews.";
            }
            {
              assertion = nav.places != [ ];
              message = "No frequent locations are declared, so the sidebar carries nothing to navigate to.";
            }
            {
              assertion = builtins.all (place: fromDeclaredRoot place.path) nav.places;
              message = "A frequent location is not under a declared sinnix root, so the sidebar can drift from the filesystem layout.";
            }
            {
              assertion = hm.gtk.gtk3.bookmarks == expectedBookmarks;
              message = "GTK bookmarks do not render the declared places one-to-one.";
            }
            {
              assertion =
                hm.xdg.mimeApps.defaultApplications."inode/directory" or [ ] == [ nav.managerDesktopEntry ];
              message = "inode/directory is not declared, so folder opening falls to whichever installed desktop entry sorts first.";
            }
            {
              assertion = builtins.all (
                type: hm.xdg.mimeApps.defaultApplications.${type.mime} or [ ] == [ type.handler ]
              ) representativeHandlers;
              message = "A representative content type lost its declared handler.";
            }
            {
              assertion =
                config.xdg.portal.config.hyprland."org.freedesktop.impl.portal.FileChooser" or null == "gtk";
              message = "The Hyprland portal configuration does not name a FileChooser backend.";
            }
            {
              assertion = lib.hasInfix "org.freedesktop.impl.portal.FileChooser=gtk" hyprlandPortalConf;
              message = "The rendered hyprland-portals.conf does not select the GTK FileChooser backend.";
            }
            {
              assertion = portalDirUnits == { };
              message = "A user unit sets XDG_DESKTOP_PORTAL_DIR, which replaces the portal's entire configuration and backend search with one directory and silently reverts every interface to the built-in fallbacks.";
            }
            {
              assertion =
                !(config.environment.sessionVariables ? XDG_DESKTOP_PORTAL_DIR)
                && !(config.environment.variables ? XDG_DESKTOP_PORTAL_DIR)
                && !(hm.home.sessionVariables ? XDG_DESKTOP_PORTAL_DIR);
              message = "A session variable sets XDG_DESKTOP_PORTAL_DIR, which makes xdg.portal.config inert.";
            }
          ];
      };

      evaluated = evalTestSpec system spec;
      inherit (evaluated) config;
      hm = hmFor config;
      nav = navOf config;

      helperEnv = pkgs.buildEnv {
        name = "sinnix-file-preview-helpers";
        paths = nav.previewHelpers;
      };

      # GIO only accepts a desktop entry as the default handler when its Exec
      # binary resolves, so the handlers' bin directories belong in the env.
      handlerEnv = pkgs.buildEnv {
        name = "sinnix-file-handler-entries";
        paths = [ nav.manager ] ++ nav.previewHelpers ++ competingHandlers;
        pathsToLink = [
          "/bin"
          "/share/applications"
          "/share/mime"
        ];
        ignoreCollisions = true;
      };
    in
    {
      checks.desktop-file-navigation = pkgs.runCommand "sinnix-desktop-file-navigation" { } ''
        cat > "$out" <<'EOF_CONTRACT'
        ${builtins.toJSON {
          manager = nav.manager.name;
          managerDesktopEntry = nav.managerDesktopEntry;
          previewHelpers = map (helper: helper.name) nav.previewHelpers;
          places = nav.places;
          bookmarks = hm.gtk.gtk3.bookmarks;
          fileChooser = config.xdg.portal.config.hyprland."org.freedesktop.impl.portal.FileChooser";
        }}
        EOF_CONTRACT
      '';

      # Every content type the manager cannot decode itself must be claimed by
      # a declared helper, and that helper's registered command must actually
      # produce a thumbnail for a real file of that type.
      checks.desktop-file-navigation-previews = mkRuntimeCheck system {
        name = "desktop-file-navigation-previews";
        nativeBuildInputs = [
          pkgs.python3
          pkgs.file
        ];
        script = ''
          python3 ${./desktop-file-navigation-previews.py} \
            ${helperEnv}/share/thumbnailers \
            ${fixtures} \
            ${lib.escapeShellArg (builtins.toJSON previewCases)}
        '';
      };

      # A clean profile: $HOME starts empty, the only bookmarks file is the
      # one Home Manager renders, and every entry resolves through GIO.
      checks.desktop-file-navigation-places = mkHmRuntimeCheck system {
        name = "desktop-file-navigation-places";
        inherit spec;
        includeHomePath = false;
        nativeBuildInputs = [
          pkgs.python3
          pkgs.glib.bin
        ];
        xdgConfigFiles = [ "gtk-3.0/bookmarks" ];
        script = ''
          export GIO_USE_VFS=local
          python3 ${./desktop-file-navigation-places.py} \
            "$XDG_CONFIG_HOME/gtk-3.0/bookmarks" \
            "$TMPDIR/roots" \
            ${lib.escapeShellArg (builtins.toJSON (map (place: place.path) nav.places))}
        '';
      };

      # The declared handlers must win over the desktop entries of packages
      # that claim the same types.
      checks.desktop-file-navigation-mime = mkHmRuntimeCheck system {
        name = "desktop-file-navigation-mime";
        inherit spec;
        includeHomePath = false;
        nativeBuildInputs = [
          pkgs.glib.bin
          pkgs.shared-mime-info
          pkgs.desktop-file-utils
        ];
        xdgConfigFiles = [ "mimeapps.list" ];
        script = ''
          export PATH="${handlerEnv}/bin:$PATH"
          export XDG_DATA_DIRS="${handlerEnv}/share:${pkgs.shared-mime-info}/share"
          export GIO_USE_VFS=local

          # Build the type -> application index the competing entries rely on,
          # so an undeclared type resolves the way it does on a live session.
          mkdir -p "$XDG_DATA_HOME/applications"
          cp ${handlerEnv}/share/applications/*.desktop "$XDG_DATA_HOME/applications/"
          update-desktop-database "$XDG_DATA_HOME/applications"

          assert_default() {
            local mime="$1" expected="$2" actual
            actual=$(gio mime "$mime" | sed -n '1s/.*: //p')
            if [ "$actual" != "$expected" ]; then
              echo "default handler for $mime is '$actual', expected '$expected'" >&2
              gio mime "$mime" >&2
              exit 1
            fi
            echo "ok $mime -> $actual"
          }

          assert_default inode/directory ${nav.managerDesktopEntry}
          assert_default application/pdf org.qutebrowser.qutebrowser.desktop
        '';
      };
    };
}
