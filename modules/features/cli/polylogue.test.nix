{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "cli-polylogue";
  feature = "sinnix.features.cli.polylogue.enable";
  assertions =
    config:
    let
      packageNames = map (pkg: pkg.name or "") (hmFor config).home.packages;
    in
    [
      {
        assertion =
          builtins.any (name: lib.hasPrefix "polylogue" name) packageNames
          && builtins.any (name: lib.hasPrefix "polylogue-python" name) packageNames
          && builtins.any (name: lib.hasPrefix "polylogued" name) packageNames;
        message = "Polylogue feature must install the packaged Polylogue CLI, API, and daemon wrappers";
      }
    ];
}
