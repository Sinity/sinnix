# Core Desktop Foundation
#
# Provides:
# - Systemd-managed user services (tray, clipboard, notifications)
# - Wayland session environment and auto-start logic
# - Application launcher (tofi)
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "base"
  ];
  description = "Essential desktop background services and session logic";
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      ...
    }:
    let
      graphicalTarget = "graphical-session.target";
      stylixColors = config.lib.stylix.colors;
      toRgba = alpha: color: "${lib.removePrefix "#" color}${alpha}";
      bg = toRgba "f0" stylixColors.base00;
      border = toRgba "ff" stylixColors.base03;
      text = toRgba "ff" stylixColors.base06;
      subtle = toRgba "ff" stylixColors.base04;
      accent = toRgba "ff" stylixColors.base0D;
      criticalBg = toRgba "f0" stylixColors.base08;
      fontMono = "SauceCodePro Nerd Font Mono:size=16";
    in
    {
      home-manager.users.${user} = {
        home.packages = with pkgs; [
          clipse
          wl-clipboard
        ];

        # Clipboard
        services.clipse = {
          enable = true;
          historySize = 99999;
          allowDuplicates = false;
          systemdTarget = graphicalTarget;
          imageDisplay = {
            type = "kitty";
            scaleX = 9;
            scaleY = 9;
            heightCut = 2;
          };
        };

        # Notifications
        stylix.targets.fnott.enable = false;
        services.fnott = {
          enable = true;
          settings = {
            main = {
              notification-margin = 8;
              anchor = "top-right";
              layer = "overlay";
              max-width = 400;
              border-size = 2;
              border-radius = 10;
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
            critical = {
              background = criticalBg;
              border-color = accent;
            };
          };
        };

        # Launcher
        programs.tofi = {
          enable = true;
          settings = {
            width = 2000;
            height = 1000;
            anchor = "center";
            prompt-text = "> ";
            fuzzy-match = true;
            terminal = "kitty";
          };
        };

        # Background Services
        systemd.user.services = {
          wl-clip-persist = lib.sinnix.systemd.mkGraphicalUserService {
            description = "Wayland clipboard persistence";
            execStart = "${pkgs.wl-clip-persist}/bin/wl-clip-persist --clipboard both";
          };
          nm-applet = lib.sinnix.systemd.mkGraphicalUserService {
            description = "NetworkManager applet";
            execStart = "${pkgs.networkmanagerapplet}/bin/nm-applet";
          };
          polkit-gnome-authentication-agent-1 = lib.sinnix.systemd.mkGraphicalUserService {
            description = "polkit-gnome-authentication-agent-1";
            execStart = "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1";
          };
          blueman-applet = lib.sinnix.systemd.mkGraphicalUserService {
            description = "Blueman applet";
            execStart = "${pkgs.blueman}/bin/blueman-applet";
          };
        };

        home.sessionVariables = {
          XDG_SESSION_TYPE = "wayland";
          QT_QPA_PLATFORM = "wayland";
          SDL_VIDEODRIVER = "wayland,x11";
          CLUTTER_BACKEND = "wayland";
        };
      };
    };
} args
