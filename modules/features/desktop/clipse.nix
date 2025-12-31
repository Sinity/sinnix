{ pkgs, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [ "desktop" "clipse" ];
  description = "Clipse clipboard manager";
  configFn =
    { config, pkgs, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      home-manager.users.${user} = { ... }: {
        home.packages = [ pkgs.clipse ];

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
      };
    };
} args
