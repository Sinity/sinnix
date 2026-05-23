{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-ui";
  feature = "sinnix.features.desktop.ui.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      portalNames = map (pkg: pkg.name or (builtins.toString pkg)) config.xdg.portal.extraPortals;
      hmPackageNames = map (pkg: pkg.name or (builtins.toString pkg)) hm.home.packages;
    in
    [
      {
        assertion = config.xdg.portal.enable;
        message = "Desktop UI must enable the system xdg-desktop-portal stack";
      }
      {
        assertion =
          builtins.length portalNames == 2
          && builtins.any (lib.hasPrefix "xdg-desktop-portal-hyprland-") portalNames
          && builtins.any (lib.hasPrefix "xdg-desktop-portal-gtk-") portalNames;
        message = "Desktop UI must expose each system portal backend exactly once";
      }
      {
        assertion = hm.xdg.portal.enable == false;
        message = "Home Manager must not duplicate system portal DBus activation files";
      }
      {
        assertion = !builtins.any (lib.hasPrefix "xdg-desktop-portal-") hmPackageNames;
        message = "Home Manager packages must not re-export portal DBus activation files";
      }
    ];
}
