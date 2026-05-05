{
  lib,
  mkFeatureTest,
  hmFor,
  inputs,
  ...
}:
mkFeatureTest {
  name = "desktop-common-apps";
  feature = "sinnix.features.desktop.common-apps.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      packageNames = map (pkg: pkg.name or "") hm.home.packages;
      yaziConfig = builtins.readFile (inputs.self + "/dots/yazi/yazi.toml");
    in
    [
      {
        assertion = hm.xdg.configFile ? "yazi/yazi.toml";
        message = "Common desktop apps must link the Yazi config";
      }
      {
        assertion = hm.xdg.configFile ? "yazi/plugins/sinnix-video-preview.yazi/main.lua";
        message = "Common desktop apps must link the custom Yazi video preview plugin";
      }
      {
        assertion = builtins.any (name: lib.hasPrefix "media-preview-cache" name) packageNames;
        message = "Common desktop apps must install the media preview cache helper";
      }
      {
        assertion =
          lib.hasInfix "image_delay = 0" yaziConfig
          && lib.hasInfix "run = \"sinnix-video-preview\"" yaziConfig;
        message = "Yazi must use the custom instant video preview configuration";
      }
    ];
}
