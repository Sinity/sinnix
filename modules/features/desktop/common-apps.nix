{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.common-apps;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.common-apps = {
    enable = lib.mkEnableOption "Common Desktop Applications and Settings";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} =
      {
        pkgs,
        lib,
        config,
        dotsRepoPath,
        helpers,
        ...
      }:
      let
        mkDotsRepoLink = helpers.mkDotsSymlink config dotsRepoPath;
      in
      {
        home.packages = with pkgs; [
          junction
          nautilus
          bleachbit
          transmission_4-gtk
          pwvucontrol
          weechat
          piper
          solaar
          android-file-transfer
          soundwireserver
          kdePackages.kdeconnect-kde
          imgur-screenshot
          aria2
          lnch
        ];

        home.file = {
          ".local/bin/imgur-screenshot" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              NO_NOTIFY_DIR="$HOME/.local/lib/imgur-screenshot/no-notify"
              if [ -d "$NO_NOTIFY_DIR" ]; then
                export PATH="$NO_NOTIFY_DIR:$PATH"
              fi

              exec "${lib.getExe pkgs.imgur-screenshot}" "$@"
            '';
            executable = true;
          };
          ".local/lib/imgur-screenshot/no-notify/notify-send" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail

              # Silence notifications for imgur-screenshot to avoid DBus errors.
              exit 0
            '';
            executable = true;
          };
        };

        xdg = {
          configFile = {
            "imgur-screenshot/settings.conf".text = ''
              OPEN="false"
              EDIT="false"
              CHECK_UPDATE="false"
            '';
            "yazi/opener.toml" = {
              source = mkDotsRepoLink "/yazi/opener.toml";
              force = true;
            };
            "yazi/keymap.toml" = {
              source = mkDotsRepoLink "/yazi/keymap.toml";
              force = true;
            };
            "audacity/audacity.cfg".source = mkDotsRepoLink "/audacity/audacity.cfg";
            "transmission/settings.json".source = mkDotsRepoLink "/transmission/settings.json";
          };
        };
      };
  };
}
