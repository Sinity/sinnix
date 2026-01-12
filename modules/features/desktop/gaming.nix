{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [ "desktop" "gaming" ];
  description = "Steam/gamemode gaming support";
  configFn =
    { config, lib, pkgs, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      programs = {
        steam = {
          enable = true;
          gamescopeSession.enable = true;
        };
        gamemode.enable = true;
      };

      home-manager.users.${user}.home.packages = with pkgs; [
        mangohud
        steam-run
      ];
    };
} args
