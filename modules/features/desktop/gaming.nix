{ lib, config, pkgs, ... }:
let
  cfg = config.sinnix.features.desktop.gaming;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.gaming = {
    enable = lib.mkEnableOption "Desktop Gaming Support (Steam/Gamemode)";
  };

  config = lib.mkIf cfg.enable {
    programs.steam = {
      enable = true;
      gamescopeSession.enable = true;
    };
    programs.gamemode.enable = true;

    home-manager.users.${user}.home.packages = with pkgs; [
      mangohud
      steam-run
    ];
  };
}
