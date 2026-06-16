{
  mkFeatureTest,
  ...
}:
mkFeatureTest {
  name = "desktop-media";
  feature = "sinnix.features.desktop.media.enable";
  assertions = _config: [ ];
}
