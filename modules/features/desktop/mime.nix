{ mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "mime"
  ];
  description = "Desktop MIME associations";
  configFn =
    {
      config,
      lib,
      user,
      ...
    }:
    let
      browserHandlerDesktop = "sinnix-browser-link.desktop";
      browserMimeTypes = [
        "text/html"
        "x-scheme-handler/http"
        "x-scheme-handler/https"
        "x-scheme-handler/about"
        "x-scheme-handler/unknown"
      ];
      # Shared media associations - used for both added and default
      mediaAssociations = {
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

      # Browser handlers (only in defaultApplications)
      browserHandlers = lib.genAttrs browserMimeTypes (_: [ browserHandlerDesktop ]);
    in
    {
      home-manager.users.${user} =
        { config, ... }:
        {
          xdg.desktopEntries.sinnix-browser-link = {
            name = "Sinnix Browser Link";
            genericName = "Web Browser";
            comment = "Open browser links without swallowing the calling terminal";
            exec = "${config.home.homeDirectory}/.local/bin/open-browser-link %U";
            terminal = false;
            noDisplay = true;
            categories = [
              "Network"
              "WebBrowser"
            ];
            mimeType = browserMimeTypes;
          };

          xdg.mimeApps = {
            enable = true;
            associations.added = mediaAssociations;
            associations.removed = {
              "video/mp4" = [ "svp-manager4.desktop" ];
              "video/mkv" = [ "svp-manager4.desktop" ];
              "video/webm" = [ "svp-manager4.desktop" ];
              "video/x-matroska" = [ "svp-manager4.desktop" ];
            };
            defaultApplications = mediaAssociations // browserHandlers;
          };
        };
    };
} args
