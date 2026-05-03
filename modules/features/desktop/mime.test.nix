{ mkFeatureTest, hmFor, ... }:
mkFeatureTest {
  name = "desktop-mime";
  feature = "sinnix.features.desktop.mime.enable";
  assertions =
    config:
    let
      defaultApps = (hmFor config).xdg.mimeApps.defaultApplications;
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
    ];
}
