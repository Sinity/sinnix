{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-gaming";
  feature = "sinnix.features.desktop.gaming.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      packageNames = map (pkg: pkg.name or "") hm.home.packages;
    in
    [
      {
        assertion = builtins.any (name: name == "factorio-steam") packageNames;
        message = "Gaming feature must install the factorio-steam launcher";
      }
    ];
}
