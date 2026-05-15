{
  lib,
  mkFeatureTest,
  hmFor,
  inputs,
  ...
}:
mkFeatureTest {
  name = "desktop-browser";
  feature = "sinnix.features.desktop.browser.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      quteConfig = builtins.readFile (inputs.self + "/dots/qutebrowser/config.py");
      chromePkgs = builtins.filter (pkg: (pkg.pname or "") == "google-chrome") hm.home.packages;
      chromePkg = if chromePkgs == [ ] then null else builtins.head chromePkgs;
      chromeLauncherPkgs = builtins.filter (
        pkg: lib.hasPrefix "sinnix-chrome" (pkg.name or "")
      ) hm.home.packages;
      chromeLauncher = if chromeLauncherPkgs == [ ] then null else builtins.head chromeLauncherPkgs;
      chromeDesktop =
        if chromePkg == null then
          ""
        else
          builtins.readFile "${chromePkg}/share/applications/google-chrome.desktop";
      chromeWrapper =
        if chromePkg == null then "" else builtins.readFile "${chromePkg}/bin/google-chrome-stable";
      chromeLauncherScript =
        if chromeLauncher == null then "" else builtins.readFile "${chromeLauncher}/bin/sinnix-chrome";
      localChromeDesktop = hm.xdg.desktopEntries.google-chrome;
      localChromeExec = builtins.unsafeDiscardStringContext localChromeDesktop.exec;
      browserLinkScript = builtins.readFile (inputs.self + "/scripts/open-browser-link");
    in
    [
      {
        assertion = hm.xdg.configFile ? "qutebrowser/config.py";
        message = "Qutebrowser config must be linked";
      }
      {
        assertion = builtins.match ".*configfiles\\.read_autoconfig.*" quteConfig == null;
        message = "Qutebrowser config must target the pinned modern API directly";
      }
      {
        assertion = builtins.match ".*except Exception:.*" quteConfig == null;
        message = "Qutebrowser config must not silently swallow broad exceptions";
      }
      {
        assertion =
          chromePkg != null
          && !(lib.hasPrefix "google-chrome-trigger-capture" (chromePkg.name or ""))
          && builtins.match ".*Exec=.*/bin/google-chrome-stable.*" chromeDesktop != null;
        message = "Chrome package must remain the normal upstream desktop package";
      }
      {
        assertion =
          lib.hasInfix "--disable-features=WaylandWpColorManagerV1,Vulkan,DefaultANGLEVulkan" chromeWrapper
          && !(lib.hasInfix "VaapiVideoDecoder" chromeWrapper)
          && !(lib.hasInfix "--disable-accelerated-video-decode" chromeWrapper)
          && !(lib.hasInfix "--disable-zero-copy" chromeWrapper);
        message = "Chrome must keep video acceleration defaults while disabling Wayland color/Vulkan GPU-reset bugs";
      }
      {
        assertion =
          chromeLauncher != null
          && lib.hasInfix "systemd-run" chromeLauncherScript
          && lib.hasInfix "--slice=app.slice" chromeLauncherScript
          && lib.hasInfix "--property=ExitType=cgroup" chromeLauncherScript
          && lib.hasInfix "SINNIX_CHROME_SCOPED" chromeLauncherScript
          && lib.hasInfix "google-chrome-stable" chromeLauncherScript;
        message = "Chrome launcher must put browser and renderer descendants in one app cgroup";
      }
      {
        assertion =
          lib.hasSuffix "/bin/sinnix-chrome %U" localChromeExec
          && localChromeDesktop.icon == "google-chrome"
          && builtins.elem "x-scheme-handler/https" localChromeDesktop.mimeType;
        message = "Local Chrome desktop entry must override tofi-drun launches with the scoped launcher";
      }
      {
        assertion =
          lib.hasInfix "browser_cmd=\"\${SINNIX_BROWSER_COMMAND:-sinnix-chrome}\"" browserLinkScript
          && lib.hasInfix "browser_cmd=google-chrome-stable" browserLinkScript;
        message = "open-browser-link must prefer the scoped Chrome launcher with upstream fallback";
      }
    ];
}
