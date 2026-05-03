{ lib, mkFeatureTest, hmFor, inputs, ... }:
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
      chromeDesktop =
        if chromePkg == null then
          ""
        else
          builtins.readFile "${chromePkg}/share/applications/google-chrome.desktop";
      chromeWrapper =
        if chromePkg == null then "" else builtins.readFile "${chromePkg}/bin/google-chrome-stable";
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
        message = "Chrome desktop entry must point at the normal binary by default";
      }
      {
        assertion =
          lib.hasInfix "--disable-features=WaylandWpColorManagerV1" chromeWrapper
          && !(lib.hasInfix "VaapiVideoDecoder" chromeWrapper)
          && !(lib.hasInfix "--disable-accelerated-video-decode" chromeWrapper)
          && !(lib.hasInfix "--disable-zero-copy" chromeWrapper);
        message = "Chrome must keep video acceleration defaults while disabling only the Wayland color bug";
      }
    ];
}
