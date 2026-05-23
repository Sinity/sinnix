{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-base";
  feature = "sinnix.features.desktop.base.enable";
  extraModules = [
    (
      { ... }:
      {
        sinnix.machine.isDesktop = true;
        sinnix.features.desktop.ui.enable = true;
      }
    )
    (
      { pkgs, ... }:
      {
        assertions = [
          {
            assertion = pkgs.blueman.passthru.sinnixRemovesXdgAutostart or false;
            message = "Blueman XDG autostart must not duplicate the managed user service";
          }
          {
            assertion = pkgs.obex_data_server.passthru.sinnixRenamesDbusActivation or false;
            message = "OBEX DBus activation file name must match its DBus name";
          }
        ];
      }
    )
  ];
  assertions =
    config:
    let
      hm = hmFor config;
      fnottPackage = hm.services.fnott.package;
    in
    [
      {
        assertion = hm.services.fnott.enable;
        message = "Desktop base must enable fnott notifications";
      }
      {
        assertion = fnottPackage.passthru.sinnixRemovesDbusActivation or false;
        message = "Fnott package must not export a duplicate DBus activation file";
      }
      {
        assertion =
          lib.hasInfix "SystemdService=fnott.service"
            hm.xdg.dataFile."dbus-1/services/org.freedesktop.Notifications.service".text;
        message = "Fnott DBus activation must delegate to the managed systemd user service";
      }
      {
        assertion = hm.xdg.dataFile."dbus-1/services/fnott.service".enable == false;
        message = "Fnott DBus activation file name must match its DBus name";
      }
      {
        assertion = hm.xdg.userDirs.download == "${config.sinnix.paths.realmRoot}/inbox/download";
        message = "Desktop base must declare the canonical XDG download directory";
      }
    ];
}
