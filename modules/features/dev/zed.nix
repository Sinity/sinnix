{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.zed;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.zed = {
    enable = lib.mkEnableOption "Zed Editor";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { config, dotsRepoPath, ... }: 
      let
        mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + rel);
      in
      {
        xdg.configFile = {
          # Zed uses lowercase 'zed' for its config directory
          "zed/settings.json".source = mkDotsRepoLink "/zed/settings.json";
          "zed/keymap.json".source = mkDotsRepoLink "/zed/keymap.json";
        };

        home.file.".local/bin/zed" = {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail
            exec zeditor "$@"
          '';
          executable = true;
        };
      };
  };
}
