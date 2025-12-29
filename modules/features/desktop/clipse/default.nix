{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.features.desktop.clipse;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.clipse = {
    enable = lib.mkEnableOption "Clipse Clipboard Manager";
  };

  config = lib.mkIf cfg.enable {
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
}
