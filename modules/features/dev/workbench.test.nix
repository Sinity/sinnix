{ mkFeatureTest, ... }:
mkFeatureTest {
  name = "dev-workbench";
  feature = "sinnix.features.dev.workbench.enable";
  assertions = _config: [ ];
}
