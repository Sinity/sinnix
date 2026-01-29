{ mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "mime"
  ];
  description = "Desktop MIME associations";
  configFn =
    { config, lib, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      home-manager.users.${user} =
        { ... }:
        {
          xdg.mimeApps = {
            enable = true;
            associations.added = {
              "text/plain" = [ "org.gnome.TextEditor.desktop" ];
              "image/bmp" = [ "imv.desktop" ];
              "image/gif" = [ "imv.desktop" ];
              "image/jpeg" = [ "imv.desktop" ];
              "image/jpg" = [ "imv.desktop" ];
              "image/png" = [ "imv.desktop" ];
              "image/svg+xml" = [ "imv.desktop" ];
              "image/tiff" = [ "imv.desktop" ];
              "image/vnd.microsoft.icon" = [ "imv.desktop" ];
              "image/webp" = [ "imv.desktop" ];
              "audio/aac" = [ "mpv.desktop" ];
              "audio/mpeg" = [ "mpv.desktop" ];
              "audio/ogg" = [ "mpv.desktop" ];
              "audio/opus" = [ "mpv.desktop" ];
              "audio/wav" = [ "mpv.desktop" ];
              "audio/webm" = [ "mpv.desktop" ];
              "video/mp4" = [ "mpv.desktop" ];
              "video/mpeg" = [ "mpv.desktop" ];
              "video/mp2t" = [ "mpv.desktop" ];
              "video/mkv" = [ "mpv.desktop" ];
              "video/webm" = [ "mpv.desktop" ];
              "video/x-matroska" = [ "mpv.desktop" ];
              "video/x-msvideo" = [ "mpv.desktop" ];
              "video/x-flv" = [ "mpv.desktop" ];
              "video/quicktime" = [ "mpv.desktop" ];
              "video/3gpp" = [ "mpv.desktop" ];
              "video/ogg" = [ "mpv.desktop" ];
              "application/pdf" = [ "org.qutebrowser.qutebrowser.desktop" ];
            };
            associations.removed = {
              "video/mp4" = [ "svp-manager4.desktop" ];
              "video/mkv" = [ "svp-manager4.desktop" ];
              "video/webm" = [ "svp-manager4.desktop" ];
              "video/x-matroska" = [ "svp-manager4.desktop" ];
            };
            defaultApplications = {
              "text/plain" = [ "org.gnome.TextEditor.desktop" ];
              "image/bmp" = [ "imv.desktop" ];
              "image/gif" = [ "imv.desktop" ];
              "image/jpeg" = [ "imv.desktop" ];
              "image/jpg" = [ "imv.desktop" ];
              "image/png" = [ "imv.desktop" ];
              "image/svg+xml" = [ "imv.desktop" ];
              "image/tiff" = [ "imv.desktop" ];
              "image/vnd.microsoft.icon" = [ "imv.desktop" ];
              "image/webp" = [ "imv.desktop" ];
              "audio/aac" = [ "mpv.desktop" ];
              "audio/mpeg" = [ "mpv.desktop" ];
              "audio/ogg" = [ "mpv.desktop" ];
              "audio/opus" = [ "mpv.desktop" ];
              "audio/wav" = [ "mpv.desktop" ];
              "audio/webm" = [ "mpv.desktop" ];
              "video/mp4" = [ "mpv.desktop" ];
              "video/mpeg" = [ "mpv.desktop" ];
              "video/mp2t" = [ "mpv.desktop" ];
              "video/mkv" = [ "mpv.desktop" ];
              "video/webm" = [ "mpv.desktop" ];
              "video/x-matroska" = [ "mpv.desktop" ];
              "video/x-msvideo" = [ "mpv.desktop" ];
              "video/x-flv" = [ "mpv.desktop" ];
              "video/quicktime" = [ "mpv.desktop" ];
              "video/3gpp" = [ "mpv.desktop" ];
              "video/ogg" = [ "mpv.desktop" ];
              "application/pdf" = [ "org.qutebrowser.qutebrowser.desktop" ];
              "text/html" = [ "google-chrome.desktop" ];
              "x-scheme-handler/http" = [ "google-chrome.desktop" ];
              "x-scheme-handler/https" = [ "google-chrome.desktop" ];
              "x-scheme-handler/about" = [ "google-chrome.desktop" ];
              "x-scheme-handler/unknown" = [ "google-chrome.desktop" ];
            };
          };
        };
    };
} args
