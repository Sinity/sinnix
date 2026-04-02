{
  mkFeatureModule,
  pkgs,
  helpers,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "common-apps"
  ];
  description = "Common desktop applications and settings";
  configFn =
    {
      config,
      helpers,
      user,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          mkDotsFileFor,
          ...
        }:
        let
          mkDotsFile = mkDotsFileFor config;
        in
        {
          home.packages = with pkgs; [
            nautilus
            transmission_4-gtk
            pwvucontrol
            blueman
            weechat
            solaar
            imgur-screenshot
            aria2
            lnch
            libnotify
            scriptPkgs.media-preview-cache
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
                source = mkDotsFile "/yazi/opener.toml";
                force = true;
              };
              "yazi/yazi.toml" = {
                source = mkDotsFile "/yazi/yazi.toml";
                force = true;
              };
              "yazi/keymap.toml" = {
                source = mkDotsFile "/yazi/keymap.toml";
                force = true;
              };
              "yazi/plugins/sinnix-video-preview.yazi/main.lua" = {
                source = mkDotsFile "/yazi/plugins/sinnix-video-preview.yazi/main.lua";
                force = true;
              };
              "audacity/audacity.cfg".source = mkDotsFile "/audacity/audacity.cfg";
              "transmission/settings.json" = {
                source = mkDotsFile "/transmission/settings.json";
                force = true;
              };
            };
          };
        };
    };
} args
