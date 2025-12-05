# Desktop applications and services configuration
#
# This file configures:
#   - Application packages
#   - Per-app services (waybar, fnott, clipse, tofi)
#   - Custom waybar widgets
#   - QT/Kvantum theme (coordinated with stylix)
#
# Note: fnott colors are derived from stylix (see config.lib.stylix.colors)
#       but we manually configure layout/behavior
{
  pkgs,
  lib,
  dotsRepoPath,
  config,
  sinnix,
  ...
}:
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
    clipse
    fnott
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

  programs.mullvad-vpn = {
    enable = true;
    settings = {
      preferredLocale = "system";
      autoConnect = false;
      enableSystemNotifications = true;
      monochromaticIcon = false;
      startMinimized = true;
      unpinnedWindow = true;
      browsedForSplitTunnelingApplications = [ ];
      changelogDisplayedForVersion = "2025.2";
      animateMap = true;
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

  home.activation.cleanupKvantum = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
    rm -rf "$HOME/.config/Kvantum"
  '';

  services.clipse = {
    enable = true;
    historySize = 99999;
    allowDuplicates = false;
    systemdTarget = "graphical-session.target";
    imageDisplay = {
      type = "kitty";
      scaleX = 9;
      scaleY = 9;
      heightCut = 2;
    };
    keyBindings = {
      choose = "enter";
      clearSelected = "D";
      down = "j";
      up = "k";
      end = "G";
      home = "g";
      filter = "/";
      more = "?";
      nextPage = "l";
      prevPage = "h";
      preview = "v";
      quit = "q";
      remove = "d";
      selectDown = "J";
      selectUp = "K";
      selectSingle = "V";
      togglePin = "m";
      togglePinned = "M";
      yankFilter = "y";
    };
  };

  stylix.targets.fnott.enable = false;
  stylix.targets.qt.enable = false;

  services.fnott =
    let
      stylixColors = config.lib.stylix.colors;
      toRgba =
        alpha: color:
        let
          hex = lib.removePrefix "#" color;
        in
        "${hex}${alpha}";
      bg = toRgba "f0" stylixColors.base00;
      border = toRgba "ff" stylixColors.base03;
      text = toRgba "ff" stylixColors.base06;
      subtle = toRgba "ff" stylixColors.base04;
      accent = toRgba "ff" stylixColors.base0D;
      criticalBg = toRgba "f0" stylixColors.base08;
      fontMono = "SauceCodePro Nerd Font Mono:size=16";
    in
    {
      enable = true;
      settings = {
        main = {
          notification-margin = 8;
          anchor = "top-right";
          layer = "overlay";
          max-width = 400;
          max-height = 240;
          min-width = 320;
          border-size = 2;
          border-radius = 10;
          padding-horizontal = 14;
          padding-vertical = 10;
          progress-bar-height = 4;
          dpi-aware = true;
          background = bg;
          border-color = border;
          title-font = fontMono;
          title-color = text;
          summary-font = fontMono;
          summary-color = text;
          body-font = fontMono;
          body-color = subtle;
          progress-color = accent;
        };
        low = {
          background = bg;
          title-color = subtle;
          summary-color = subtle;
          body-color = subtle;
          default-timeout = 5;
        };
        normal = {
          background = bg;
          title-color = text;
          summary-color = text;
          body-color = subtle;
          default-timeout = 10;
        };
        critical = {
          background = criticalBg;
          border-color = accent;
          title-color = text;
          summary-color = text;
          body-color = text;
          default-timeout = 0;
        };
      };
    };

  programs.tofi = {
    enable = true;
    settings = {
      width = 2000;
      height = 1000;
      anchor = "center";
      horizontal = false;
      num-results = 0;
      result-spacing = 4;
      padding-top = 20;
      padding-bottom = 20;
      padding-left = 20;
      padding-right = 20;
      prompt-text = "> ";
      prompt-padding = 8;
      history = true;
      hide-cursor = true;
      text-cursor = true;
      fuzzy-match = true;
      late-keyboard-init = false;
      multi-instance = false;
      terminal = "kitty";
    };
  };

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
      "autostart/mullvad-vpn.desktop".text = ''
        [Desktop Entry]
        Type=Application
        Name=Mullvad VPN (disabled)
        Hidden=true
      '';
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
}
