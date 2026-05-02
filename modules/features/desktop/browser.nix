{
  mkFeatureModule,
  pkgs,
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
      user,
      ...
    }:
    let
      repoRoot = config.sinnix.paths.projectRoot;
    in
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
          # Also disable Vulkan/ANGLE-Vulkan and Chrome's accelerated video
          # decode/zero-copy paths. On 2026-05-02, rapidly switching YouTube
          # tabs hit NVIDIA DRM BAR mapping failures (`NV_ERR_NO_MEMORY` from
          # `reusemappingdbMap`) followed by Chrome Media renderer SIGILLs and
          # Xid 44. Keep GPU compositing, but route video frames away from the
          # dmabuf/BAR-heavy path that crashed the display stack.
          #
          # --user-data-dir is intentional: Chrome 136+ silently refuses to
          # honour --remote-debugging-port when using the platform-default
          # profile path (~/.config/google-chrome). Pointing at a non-default
          # directory restores debug-port behaviour. See:
          # https://developer.chrome.com/blog/remote-debugging-port
          # Side effect: loopback-only debug port allows local processes to
          # read cookies via CDP. Acceptable on this single-user machine.
          chromeUserDataDir = "${config.home.homeDirectory}/.config/chrome-ws";
          chromeArgs = lib.concatStringsSep " " [
            "--disable-features=WaylandWpColorManagerV1,Vulkan,DefaultANGLEVulkan,VaapiVideoDecoder,VaapiVideoEncoder,UseChromeOSDirectVideoDecoder"
            "--disable-accelerated-video-decode"
            "--disable-gpu-memory-buffer-video-frames"
            "--disable-zero-copy"
            "--remote-debugging-port=9222"
            "--remote-debugging-address=127.0.0.1"
            "--user-data-dir=${chromeUserDataDir}"
          ];
          chromePkg = pkgs.google-chrome.override {
            commandLineArgs = chromeArgs;
          };
          browserLinkCmd = "${config.home.homeDirectory}/.local/bin/open-browser-link";
          mkDotsFile = mkDotsFileFor config;
          quteDots = rel: mkDotsFile ("/qutebrowser" + rel);
          mkUserScript = name: {
            source = quteDots ("/userscripts/" + name);
          };
        in
        {
          home = {
            sessionVariables = {
              BROWSER = browserLinkCmd;
            };

            packages = with pkgs; [
              chromePkg
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
