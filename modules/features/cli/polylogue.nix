{
  mkFeatureModule,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "polylogue"
  ];
  description = "Polylogue commands over the live archive";
  configFn =
    {
      user,
      lib,
      pkgs,
      inputs,
      config,
      ...
    }:
    let
      cli = import ../../lib/polylogue-cli.nix {
        inherit
          lib
          pkgs
          inputs
          config
          ;
      };
    in
    {
      system.build.polylogueCli = cli;
      home-manager.users.${user}.home.packages = [ cli ];
    };
} args
