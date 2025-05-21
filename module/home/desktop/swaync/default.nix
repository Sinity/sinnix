# module/desktop/swaync/default.nix
{ pkgs, ... }:
{
  home.packages = [ pkgs.swaynotificationcenter ];

  xdg.configFile."swaync/style.css".source = ./style.css;
  xdg.configFile."swaync/config.json".source = ./config.json;
}
