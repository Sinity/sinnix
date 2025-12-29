{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.tofi;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.tofi = {
    enable = lib.mkEnableOption "Tofi Application Launcher";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { ... }: {
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
    };
  };
}
