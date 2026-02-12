{
  mkFeatureModule,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "gaming"
  ];
  description = "Gaming support (Steam, gamemode, tools)";
  subFeatures = {
    steam = {
      description = "Steam platform with gamescope session";
      default = true;
    };
    gamemode = {
      description = "Feral gamemode for performance optimization";
      default = true;
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      cfg,
      user,
      ...
    }:
    lib.mkMerge [
      # Steam with gamescope
      (lib.mkIf cfg.steam.enable {
        programs.steam = {
          enable = true;
          gamescopeSession.enable = true;
        };

        home-manager.users.${user}.home.packages = with pkgs; [
          mangohud
          steam-run
        ];
      })

      # Gamemode for performance
      (lib.mkIf cfg.gamemode.enable {
        programs.gamemode.enable = true;
      })
    ];
} args
