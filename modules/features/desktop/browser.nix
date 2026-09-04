{
  mkFeatureModule,
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
      repoRoot = config.sinnix.paths.projectRoot;
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
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
          chromeUserDataDir = "${config.home.homeDirectory}/.config/chrome-ws";
          navCaptureExtension = pkgs.runCommand "sinnix-nav-capture-extension" { } ''
            mkdir -p "$out"
            cp -R ${../../../browser-extensions/nav-capture}/. "$out/"
          '';
          chromeArgs = lib.concatStringsSep " " [
            "--disable-features=WaylandWpColorManagerV1"
            "--remote-debugging-port=9222"
            "--remote-debugging-address=127.0.0.1"
            "--user-data-dir=${chromeUserDataDir}"
            "--load-extension=${navCaptureExtension}"
            # Chrome-family apps register with AT-SPI but expose an empty tree
            # unless renderer accessibility is forced on. Without it the
            # capture-a11y lane sees focus events from Chrome windows with no
            # readable content -- and Chrome is where most of the readable
            # content on this desktop lives. See modules/services/capture-a11y.nix.
            "--force-renderer-accessibility"
          ];
          chromePkg = pkgs.google-chrome.override {
            commandLineArgs = chromeArgs;
          };
          # Launch Chrome through a transient user service so browser children
          # stay in one cgroup for accounting and interactive policy.
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
            sinnix-nav-capture = {
              Unit = {
                Description = "Sinnix browser provenance receiver";
                After = [ "graphical-session-pre.target" ];
                PartOf = [ "graphical-session.target" ];
              };
              Service = {
                ExecStart = "${scriptPkgs.sinnix-nav-capture-daemon}/bin/sinnix-nav-capture-daemon";
                Restart = "on-failure";
              };
              Install.WantedBy = [ "graphical-session.target" ];
            };
            sinnix-reading-stack-widget = {
              Unit = {
                Description = "Visible Sinnix reading stack";
                After = [ "graphical-session.target" ];
                PartOf = [ "graphical-session.target" ];
              };
              Service = {
                ExecStart = "${pkgs.uwsm}/bin/uwsm app -- ${pkgs.kitty}/bin/kitty --class reading-stack-widget --title reading-stack ${scriptPkgs.sinnix-reading-stack-widget}/bin/sinnix-reading-stack-widget";
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
    };
} args
