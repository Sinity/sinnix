{
  config,
  dotsRepoPath,
  ...
}:
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
}
