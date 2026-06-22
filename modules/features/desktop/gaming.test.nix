{ mkFeatureTest, ... }:
mkFeatureTest {
  name = "desktop-gaming";
  feature = "sinnix.features.desktop.gaming.enable";
  assertions = _config: [ ];
}
