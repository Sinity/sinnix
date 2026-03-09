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
  configFn =
    {
      config,
      lib,
      pkgs,
      helpers,
      user,
      ...
    }:
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          mkDotsFileFor,
          ...
        }:
        let
          # Disable Chromium's Wayland color management - it conflicts with
          # Hyprland's HDR mode, causing washed out colors.
          # See: https://github.com/hyprwm/Hyprland/discussions/11910
          #
          # Also disable Vulkan/ANGLE-Vulkan to avoid unstable paths on
          # NVIDIA+Wayland+HDR setups while keeping normal GPU acceleration.
          chromeArgs = lib.concatStringsSep " " [
            "--disable-features=WaylandWpColorManagerV1,Vulkan,DefaultANGLEVulkan"
          ];
          chromeStablePkg = pkgs.google-chrome.override {
            commandLineArgs = chromeArgs;
          };
          mkDotsFile = mkDotsFileFor config;
          quteDots = rel: mkDotsFile ("/qutebrowser" + rel);
          mkUserScript = name: {
            source = quteDots ("/userscripts/" + name);
          };
        in
        {
          home = {
            sessionVariables = {
              BROWSER = "google-chrome-stable";
            };

            packages = with pkgs; [
              chromeStablePkg
              qutebrowser
              tor-browser
            ];

            file = {
              ".local/share/qutebrowser/userscripts/open-in-mpv" = mkUserScript "open-in-mpv";
              ".local/share/qutebrowser/userscripts/open-in-mpv-audio" = mkUserScript "open-in-mpv-audio";
              ".local/share/qutebrowser/userscripts/yt-related" = mkUserScript "yt-related";
              ".local/share/qutebrowser/userscripts/archive-both" = mkUserScript "archive-both";
              ".local/share/qutebrowser/userscripts/raindrop-save" = mkUserScript "raindrop-save";
              ".local/share/qutebrowser/userscripts/research-capture" = mkUserScript "research-capture";
            };

            activation."qutebrowser-userscripts-perms" = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              for script in \
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

          xdg.configFile = {
            "qutebrowser/config.py".source = quteDots "/config.py";
            "qutebrowser/user.css".source = quteDots "/user.css";
            "qutebrowser/greasemonkey/cookie-nag-zapper.user.js".source =
              quteDots "/greasemonkey/cookie-nag-zapper.user.js";
            "qutebrowser/greasemonkey/readable-medium.user.js".source =
              quteDots "/greasemonkey/readable-medium.user.js";
            "qutebrowser/greasemonkey/template.user.js".source = quteDots "/greasemonkey/template.user.js";
          };
        };
    };
} args
