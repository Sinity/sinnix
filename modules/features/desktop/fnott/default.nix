{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.fnott;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.fnott = {
    enable = lib.mkEnableOption "Fnott Notification Daemon";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { config, lib, ... }: {
      stylix.targets.fnott.enable = false;
      
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
    };
  };
}
