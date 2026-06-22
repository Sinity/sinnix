{ mkFeatureTest, hmFor, ... }:
mkFeatureTest {
  name = "desktop-common-apps";
  feature = "sinnix.features.desktop.common-apps.enable";
  assertions =
    config:
    let
      hm = hmFor config;
    in
    [
      {
        assertion = hm.xdg.configFile ? "yazi/plugins/sinnix-video-preview.yazi/main.lua";
        message = "Common desktop apps must link the custom Yazi video preview plugin";
      }
    ];
}
