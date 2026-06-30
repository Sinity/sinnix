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
  description = "Packaged Polylogue operator commands";
  configFn =
    {
      user,
      pkgs,
      helpers,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
      home-manager.users.${user} = _: {
        home.packages = [
          scriptPkgs.polylogue-cli
          scriptPkgs.polylogue-python
          scriptPkgs.polylogued
        ];
      };
    };
} args
