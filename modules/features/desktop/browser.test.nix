{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-browser";
  feature = "sinnix.features.desktop.browser.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      chromePkgs = builtins.filter (pkg: (pkg.pname or "") == "google-chrome") hm.home.packages;
      chromePkg = if chromePkgs == [ ] then null else builtins.head chromePkgs;
      chromeLauncherPkgs = builtins.filter (
        pkg: lib.hasPrefix "sinnix-chrome" (pkg.name or "")
      ) hm.home.packages;
      chromeLauncher = if chromeLauncherPkgs == [ ] then null else builtins.head chromeLauncherPkgs;
      localChromeDesktop = hm.xdg.desktopEntries.google-chrome;
      localChromeExec = builtins.unsafeDiscardStringContext localChromeDesktop.exec;
    in
    [
      {
        assertion = hm.xdg.configFile ? "qutebrowser/config.py";
        message = "Qutebrowser config must be linked";
      }
      {
        assertion =
          chromePkg != null && !(lib.hasPrefix "google-chrome-trigger-capture" (chromePkg.name or ""));
        message = "Chrome package must remain the normal upstream desktop package";
      }
      {
        assertion = chromeLauncher != null;
        message = "Chrome launcher must put browser and renderer descendants in one app cgroup";
      }
      {
        assertion =
          lib.hasSuffix "/bin/sinnix-chrome %U" localChromeExec
          && localChromeDesktop.icon == "google-chrome"
          && builtins.elem "x-scheme-handler/https" localChromeDesktop.mimeType;
        message = "Local Chrome desktop entry must override default launches with the scoped launcher";
      }
      {
        assertion =
          hm.home.sessionVariables.SINNIX_POLYLOGUE_BROWSER_EXTENSION_DIR
          == "/realm/project/polylogue/browser-extension";
        message = "Chrome must know the Polylogue browser-capture extension checkout path";
      }
    ];
}
