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
      inputs,
      pkgs,
      ...
    }:
    let
      scriptPkgs = inputs.self.packages.${pkgs.stdenv.hostPlatform.system};
    in
    {
      home-manager.users.${user} =
        { ... }:
        {
          home.packages = [
            scriptPkgs.polylogue-cli
            scriptPkgs.polylogue-python
          ];
        };
    };
} args
