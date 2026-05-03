{ mkBundleTest, ... }:
mkBundleTest {
  name = "bundle-desktop";
  bundle = "desktop";
  extraModules = [
    (
      { lib, pkgs, ... }:
      {
        # why mkForce: hermetic-test override. The desktop bundle enables
        # hardware.graphics for the live host; a headless eval cannot rely
        # on the real GPU stack. Provide stubbed mesa packages so the
        # graphics module's option assertions still type-check.
        hardware.graphics.enable = lib.mkForce false;
        hardware.graphics.package = lib.mkForce pkgs.mesa;
        hardware.graphics.package32 = lib.mkForce pkgs.pkgsi686Linux.mesa;
      }
    )
  ];
  assertions = config: [
    {
      assertion = config.programs.hyprland.enable or false;
      message = "Desktop must enable hyprland";
    }
    {
      assertion = config.services.pipewire.enable or false;
      message = "Desktop must enable audio";
    }
  ];
}
