{
  mkFeatureModule,
  pkgs,
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
      ...
    }:
    {
      home-manager.users.${user} =
        { ... }:
        {
          home.packages = [ pkgs.polylogue ];
        };
    };
} args
