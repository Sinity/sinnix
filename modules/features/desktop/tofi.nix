{ mkFeatureModule, config, ... }@args:
mkFeatureModule {
  path = [ "desktop" "tofi" ];
  description = "Tofi application launcher";
  configFn =
    { config, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
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
} args
