{ lib, config, ... }:
let
  cfg = config.sinnix.features.desktop.mime;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.mime = {
    enable = lib.mkEnableOption "Desktop MIME Type Associations";
  };

  config = lib.mkIf cfg.enable {
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
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "application/pdf" = [ "org.qutebrowser.qutebrowser.desktop" ];
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
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
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
}
