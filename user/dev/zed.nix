{
  inputs,
  ...
}:
{
  xdg.configFile = {
    "Zed/settings.json".source = "${inputs.self}/dots/zed/settings.json";
    "Zed/keymap.json".source = "${inputs.self}/dots/zed/keymap.json";
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
