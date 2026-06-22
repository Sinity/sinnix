{ mkFeatureTest, ... }:
mkFeatureTest {
  name = "cli-polylogue";
  feature = "sinnix.features.cli.polylogue.enable";
  assertions = _config: [ ];
}
