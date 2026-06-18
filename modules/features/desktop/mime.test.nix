{ mkFeatureTest, hmFor, ... }:
mkFeatureTest {
  name = "desktop-mime";
  feature = "sinnix.features.desktop.mime.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      defaultApps = hm.xdg.mimeApps.defaultApplications;
      dataFiles = hm.xdg.dataFile;
    in
    [
      {
        assertion = defaultApps."x-scheme-handler/http" == [ "google-chrome.desktop" ];
        message = "HTTP links must default to Google Chrome";
      }
      {
        assertion = defaultApps."x-scheme-handler/https" == [ "google-chrome.desktop" ];
        message = "HTTPS links must default to Google Chrome";
      }
      {
        assertion = defaultApps."text/html" == [ "google-chrome.desktop" ];
        message = "HTML documents must default to Google Chrome";
      }
      {
        assertion = defaultApps."text/markdown" == [ "sinnix-text-preview.desktop" ];
        message = "Markdown documents must default to the Sinnix text preview handler";
      }
      {
        assertion = dataFiles ? "applications/sinnix-text-preview.desktop";
        message = "Sinnix text preview desktop entry must be installed";
      }
    ];
}
