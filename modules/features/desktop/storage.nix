{
  mkFeatureModule,
  pkgs,
  config,
  lib,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "storage"
  ];
  description = "User storage helpers";
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      helpers,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
      home-manager.users.${user} = {
        home.packages = with pkgs; [
          gocryptfs
          encfs
          cryptsetup
          scriptPkgs.encrypt-folder
          scriptPkgs.decrypt-folder
        ];

        xdg.configFile."autostart/git-annex.desktop".text = ''
          [Desktop Entry]
          Type=Application
          Name=Git Annex Assistant
          Hidden=true
        '';
      };
    };
} args
