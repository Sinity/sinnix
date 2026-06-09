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
      browserDefaultDesktop = "google-chrome.desktop";
      browserMimeTypes = [
        "text/html"
        "x-scheme-handler/http"
        "x-scheme-handler/https"
        "x-scheme-handler/about"
        "x-scheme-handler/unknown"
      ];
      # Shared media associations - used for both added and default
      mediaAssociations = {
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
      browserDefaults = lib.genAttrs browserMimeTypes (_: [ browserDefaultDesktop ]);

      # Open text/source files in a floating, dismissable bat preview popup
      # (scripts/open-text-preview) instead of letting them fall back to
      # nvim.desktop, whose Terminal=true entry under bare Hyprland spawns a
      # headless, window-less, immortal nvim per open. The matching Hyprland
      # float rule (app-id sinnix-preview) lives in hyprland/rules.nix.
      repoRoot = config.sinnix.paths.projectRoot;
      textPreviewTypes = [
        "text/plain"
        "text/markdown"
        "text/x-makefile"
        "text/x-csrc"
        "text/x-chdr"
        "text/x-c++src"
        "text/x-c++hdr"
        "text/x-c"
        "text/x-c++"
        "text/x-java"
        "text/x-python"
        "text/x-tex"
        "text/x-shellscript"
        "application/x-shellscript"
        "application/json"
        "application/toml"
      ];
      previewAssociations = lib.genAttrs textPreviewTypes (_: [ "sinnix-text-preview.desktop" ]);
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

          xdg.desktopEntries.sinnix-text-preview = {
            name = "Sinnix Text Preview";
            genericName = "Text Viewer";
            comment = "Open text files in a floating, dismissable preview popup";
            exec = "${config.home.homeDirectory}/.local/bin/open-text-preview %F";
            terminal = false;
            noDisplay = true;
            categories = [
              "Utility"
              "TextEditor"
            ];
            mimeType = textPreviewTypes;
          };

          home.file.".local/bin/open-text-preview" = {
            source = config.lib.file.mkOutOfStoreSymlink "${repoRoot}/scripts/open-text-preview";
            force = true;
          };

          xdg.mimeApps = {
            enable = true;
            associations.added = mediaAssociations // browserDefaults // previewAssociations;
            associations.removed = {
              "video/mp4" = [ "svp-manager4.desktop" ];
              "video/mkv" = [ "svp-manager4.desktop" ];
              "video/webm" = [ "svp-manager4.desktop" ];
              "video/x-matroska" = [ "svp-manager4.desktop" ];
            };
            defaultApplications = mediaAssociations // browserDefaults // previewAssociations;
          };
        };
    };
} args
