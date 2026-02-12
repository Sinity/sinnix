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
      inputs,
      ...
    }:
    let
      # Script packages from flake registry
      scriptPkgs = inputs.self.packages.${pkgs.stdenv.hostPlatform.system};
    in
    {
      home-manager.users.${user}.home.packages = with pkgs; [
        gocryptfs
        encfs
        cryptsetup
        scriptPkgs.encrypt-folder
        scriptPkgs.decrypt-folder
        scriptPkgs.mount-nextcloud
        scriptPkgs.umount-nextcloud
      ];
    };
} args
