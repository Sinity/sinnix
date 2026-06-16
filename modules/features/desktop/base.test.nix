{
  mkFeatureTest,
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
  assertions = _config: [ ];
}
