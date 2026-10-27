{
  mkFeatureModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "browser"
  ];
  description = "Qutebrowser + Chrome stack";
  extraOptions = {
    chromeUserDataDir = lib.mkOption {
      type = lib.types.str;
      default = ".config/chrome-ws";
      readOnly = true;
      description = ''
        Chrome's profile directory, relative to the home directory. Native
        messaging host manifests go in its `NativeMessagingHosts`.
      '';
    };
  };
  meta.dotfiles = {
    configFile = {
      "qutebrowser/config.py" = "qutebrowser/config.py";
      "qutebrowser/user.css" = "qutebrowser/user.css";
      "qutebrowser/greasemonkey/cookie-nag-zapper.user.js" =
        "qutebrowser/greasemonkey/cookie-nag-zapper.user.js";
      "qutebrowser/greasemonkey/readable-medium.user.js" =
        "qutebrowser/greasemonkey/readable-medium.user.js";
    };
    homeFile = {
      ".local/share/qutebrowser/userscripts/open-in-mpv" = "qutebrowser/userscripts/open-in-mpv";
      ".local/share/qutebrowser/userscripts/open-in-mpv-audio" =
        "qutebrowser/userscripts/open-in-mpv-audio";
      ".local/share/qutebrowser/userscripts/yt-related" = "qutebrowser/userscripts/yt-related";
      ".local/share/qutebrowser/userscripts/archive-both" = "qutebrowser/userscripts/archive-both";
      ".local/share/qutebrowser/userscripts/raindrop-save" = "qutebrowser/userscripts/raindrop-save";
      ".local/share/qutebrowser/userscripts/research-capture" =
        "qutebrowser/userscripts/research-capture";
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      user,
      ...
    }:
    let
      nixosConfig = config;
      repoRoot = config.sinnix.paths.projectRoot;
      activityRoot = config.sinnix.paths.activityRoot;
      navigationPort = helpers.data.ports.browserNavigation;
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      # The extension's identity is the hash of the key that signed its CRX, so
      # it cannot be known before the pack runs. Emitting the archive, its
      # update manifest and the managed policy from one derivation keeps the
      # id Chrome computes and the id the policy pins identical by
      # construction; a hand-written id silently stops matching instead.
      navCaptureExtension =
        pkgs.runCommand "sinnix-capture-browser-nav-extension"
          {
            nativeBuildInputs = [
              pkgs.go-crx3
              pkgs.jq
            ];
          }
          ''
            mkdir -p "$out" extension
            cp -R ${../../../browser-extensions/nav-capture}/. extension/
            chmod -R u+w extension
            substituteInPlace extension/background.js --replace-fail \
              '127.0.0.1:8767' '127.0.0.1:${toString navigationPort}'
            crx3 pack extension --outfile "$out/nav-capture.crx"
            id="$(crx3 id "$out/nav-capture.crx")"
            printf '%s' "$id" > "$out/extension-id"
            # crx3 drops the key it just minted beside the archive. The store
            # is world readable and nothing needs this key again: a rebuild
            # mints another one and republishes the id with it.
            rm -f "$out/nav-capture.crx.pem"
            cat > "$out/updates.xml" <<XML
            <?xml version="1.0" encoding="UTF-8"?>
            <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
              <app appid="$id">
                <updatecheck codebase="file://$out/nav-capture.crx" version="0.2.0" />
              </app>
            </gupdate>
            XML
            jq -n --arg id "$id" --arg url "file://$out/updates.xml" \
              '{
                 ExtensionInstallForcelist: [ ($id + ";" + $url) ],
                 ExtensionSettings: {
                   ($id): {
                     installation_mode: "force_installed",
                     override_update_url: true,
                     update_url: $url,
                   },
                 },
               }' > "$out/policy.json"
          '';
    in
    {
      programs.chromium.enable = true;

      # Chrome merges every JSON file in its managed policy directory, so the
      # generated extension policy lands beside chromium's own extra.json.
      environment.etc."opt/chrome/policies/managed/sinnix-capture-browser-nav.json".source =
        "${navCaptureExtension}/policy.json";

      systemd.tmpfiles.rules = [
        "d ${config.sinnix.paths.capturePaths.browser-nav-edges} 0700 ${user} ${user} -"
        "d ${config.sinnix.paths.capturePaths.reading-stack} 0700 ${user} ${user} -"
      ];

      sinnix.runtime.units = {
        sinnix-capture-browser-nav = {
          unit = "sinnix-capture-browser-nav.service";
          manager = "user";
          resourceClass = "capture";
          notifyOnFailure = true;
          operatorRestart = true;
          captures = [
            {
              name = "browser-nav-edges";
              path = "${config.sinnix.paths.capturePaths.browser-nav-edges}";
              eventDriven = true;
              requiredPayloadFields = [
                "source_url"
                "target_url"
              ];
            }
            # Written by the sinnix-reading-stack CLI on every push and pop;
            # the bar shows the stack through the sinnix-bar plugin.
            {
              name = "reading-stack";
              path = "${config.sinnix.paths.capturePaths.reading-stack}";
              eventDriven = true;
              requiredPayloadFields = [
                "event"
                "url"
              ];
            }
          ];
        };
      };

      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          ...
        }:
        let
          # Hyprland owns color management on this Wayland desktop path.
          #
          # --user-data-dir is intentional: Chrome 136+ silently refuses to
          # honour --remote-debugging-port when using the platform-default
          # profile path (~/.config/google-chrome). Pointing at a non-default
          # directory restores debug-port behaviour. See:
          # https://developer.chrome.com/blog/remote-debugging-port
          # Side effect: loopback-only debug port allows local processes to
          # read cookies via CDP. Acceptable on this single-user machine.
          chromeUserDataDir = "${config.home.homeDirectory}/${nixosConfig.sinnix.features.desktop.browser.chromeUserDataDir}";
          chromeArgs = lib.concatStringsSep " " (
            [
              "--disable-features=WaylandWpColorManagerV1"
              "--remote-debugging-port=9222"
              "--remote-debugging-address=127.0.0.1"
              "--user-data-dir=${chromeUserDataDir}"
              # Chrome-family apps register with AT-SPI but expose an empty tree
              # unless renderer accessibility is forced on. Without it the
              # capture-a11y lane sees focus events from Chrome windows with no
              # readable content -- and Chrome is where most of the readable
              # content on this desktop lives. See modules/services/capture-a11y.nix.
              "--force-renderer-accessibility"
            ]
            ++ lib.optionals nixosConfig.sinnix.services.proton-openai.enable [
              (lib.escapeShellArg (
                "--proxy-pac-url=data:application/x-ns-proxy-autoconfig,"
                + lib.escapeURL nixosConfig.sinnix.services.proton-openai.pacScript
              ))
            ]
          );
          chromePkg = pkgs.google-chrome.override {
            commandLineArgs = chromeArgs;
          };
          # Launch Chrome through a transient user service so browser children
          # stay in one cgroup for accounting and interactive policy. The
          # unit claims its part of app.slice's hard memory guarantee, so
          # the browser's resident core is never reclaimed for agent work.
          chromeLauncher = pkgs.writeShellApplication {
            name = "sinnix-chrome";
            runtimeInputs = [
              pkgs.coreutils
              pkgs.systemd
            ];
            text = ''
              chrome_bin="${chromePkg}/bin/google-chrome-stable"

              if [ "''${SINNIX_CHROME_SCOPED:-0}" = "1" ]; then
                exec "$chrome_bin" "$@"
              fi

              if systemctl --user show-environment >/dev/null 2>&1; then
                unit="app-google-chrome-$(date +%s%N)"
                run_args=(
                  --user
                  --collect
                  --quiet
                  --unit="$unit"
                  --description="Google Chrome"
                  --slice=app.slice
                  --same-dir
                  --property=ExitType=cgroup
                  --property=MemoryMin=${toString helpers.data.runtimeDefaults.desktopMemory.chromeMin}M
                  --setenv=SINNIX_CHROME_SCOPED=1
                )

                for var in \
                  DISPLAY \
                  WAYLAND_DISPLAY \
                  XDG_CURRENT_DESKTOP \
                  XDG_SESSION_TYPE \
                  DBUS_SESSION_BUS_ADDRESS \
                  XAUTHORITY \
                  NIXOS_OZONE_WL
                do
                  if [ -n "''${!var:-}" ]; then
                    run_args+=(--setenv="$var=''${!var}")
                  fi
                done

                exec systemd-run "''${run_args[@]}" "$chrome_bin" "$@"
              fi

              export SINNIX_CHROME_SCOPED=1
              exec "$chrome_bin" "$@"
            '';
          };
          chromeDesktopMimeTypes = [
            "text/html"
            "x-scheme-handler/http"
            "x-scheme-handler/https"
            "x-scheme-handler/about"
            "x-scheme-handler/unknown"
          ];
          browserLinkCmd = "${config.home.homeDirectory}/.local/bin/open-browser-link";
        in
        {
          home = {
            sessionVariables = {
              BROWSER = browserLinkCmd;
            };

            packages = with pkgs; [
              chromeLauncher
              chromePkg
              qutebrowser
              tor-browser
            ];

            file = {
              ".local/bin/open-browser-link" = {
                source = config.lib.file.mkOutOfStoreSymlink "${repoRoot}/scripts/open-browser-link";
                force = true;
              };
            };

            activation."qutebrowser-userscripts-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              for script in \
                "$HOME/.local/bin/open-browser-link" \
                "$HOME/.local/share/qutebrowser/userscripts/open-in-mpv" \
                "$HOME/.local/share/qutebrowser/userscripts/open-in-mpv-audio" \
                "$HOME/.local/share/qutebrowser/userscripts/yt-related" \
                "$HOME/.local/share/qutebrowser/userscripts/archive-both" \
                "$HOME/.local/share/qutebrowser/userscripts/raindrop-save" \
                "$HOME/.local/share/qutebrowser/userscripts/research-capture"
              do
                if [ -e "$script" ]; then
                  chmod +x "$script" 2>/dev/null || true
                fi
              done
            '';
          };

          systemd.user.services = {
            sinnix-capture-browser-nav = {
              Unit = {
                Description = "Sinnix browser provenance receiver";
                After = [ "graphical-session-pre.target" ];
                PartOf = [ "graphical-session.target" ];
              };
              Service =
                lib.sinnix.mkRuntimeServiceConfig {
                  runtimeInventory = nixosConfig.sinnix.runtime.inventory;
                  unit = "sinnix-capture-browser-nav.service";
                  manager = "user";
                }
                // {
                  UMask = "0077";
                  ExecStart = "${scriptPkgs.sinnix-capture-browser-nav}/bin/sinnix-capture-browser-nav";
                  Environment = [
                    "SINNIX_NAV_CAPTURE_PORT=${toString navigationPort}"
                    "SINNIX_NAV_CAPTURE_EXTENSION_ID_FILE=${navCaptureExtension}/extension-id"
                    "SINNIX_CAPTURE_ROOT=${activityRoot}"
                  ];
                  Restart = "on-failure";
                };
              Install.WantedBy = [ "graphical-session.target" ];
            };
          };

          xdg.desktopEntries.google-chrome = {
            name = "Google Chrome";
            genericName = "Web Browser";
            comment = "Access the Internet";
            exec = "${chromeLauncher}/bin/sinnix-chrome %U";
            icon = "google-chrome";
            terminal = false;
            categories = [
              "Network"
              "WebBrowser"
            ];
            mimeType = chromeDesktopMimeTypes;
          };
        };
      sinnix.persistence.home.directories = [ ".local/state/sinnix" ];
    };
} args
