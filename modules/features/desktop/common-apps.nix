{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.common-apps;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.common-apps = {
    enable = lib.mkEnableOption "Common Desktop Applications and Settings";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, lib, config, dotsRepoPath, ... }: 
      let
        kvantumPkg =
          if lib.hasAttrByPath [ "qt6Packages" "qtstyleplugin-kvantum" ] pkgs then
            pkgs.qt6Packages.qtstyleplugin-kvantum
          else if lib.hasAttrByPath [ "libsForQt5" "kvantum" ] pkgs then
            pkgs.libsForQt5.kvantum
          else
            null;
        mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + rel);
      in
      {
        home.packages = with pkgs; [
          junction
          nautilus
          taskwarrior3
          timewarrior
          bleachbit
          transmission_4-gtk
          pwvucontrol
          bluetuith
          blueman
          evtest
          meld
          piper
          solaar
          android-tools
          android-file-transfer
          hledger
          llm
          single-file-cli
          programmer-calculator
          bc
          calc
          soundwireserver
          kdePackages.kdeconnect-kde
          imgur-screenshot
          usbview
          strace
          ltrace
          nvitop
          cage
          wayland-protocols
          vkmark
          dtach
          lnch
          at
          yazi
          glow
          aria2
          wl-clip-persist
          wl-clipboard
          libnotify
          wlr-randr
        ];

        gtk = {
          enable = true;
          iconTheme = {
            package = pkgs.papirus-icon-theme;
            name = "Papirus-Dark";
          };
        };

        qt = {
          enable = true;
          platformTheme = {
            name = "qtct";
          };
          style = {
            name = "kvantum";
          }
          // lib.optionalAttrs (kvantumPkg != null) {
            package = kvantumPkg;
          };
        };
        
        # Disable stylix management for QT to allow manual override if needed, 
        # mirroring original apps.nix logic.
        stylix.targets.qt.enable = false;

        home.activation.cleanupKvantum = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
          rm -rf "$HOME/.config/Kvantum"
        '';

        xdg = {
          configFile = {
            "yazi/opener.toml" = {
              source = mkDotsRepoLink "/yazi/opener.toml";
              force = true;
            };
            "yazi/keymap.toml" = {
              source = mkDotsRepoLink "/yazi/keymap.toml";
              force = true;
            };
            "audacity/audacity.cfg".source = mkDotsRepoLink "/audacity/audacity.cfg";
            "qt5ct/qt5ct.conf".source = mkDotsRepoLink "/qt5ct/qt5ct.conf";
            "qt6ct/qt6ct.conf".source = mkDotsRepoLink "/qt6ct/qt6ct.conf";
            "Kvantum" = {
              source = mkDotsRepoLink "/Kvantum";
            };
            "transmission/settings.json".source = mkDotsRepoLink "/transmission/settings.json";
          };
          mimeApps = {
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
  };
}
