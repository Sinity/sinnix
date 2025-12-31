{ mkFeatureModule, config, pkgs, ... }@args:
mkFeatureModule {
  path = [ "desktop" "wayland-session" ];
  description = "Wayland session environment & tools";
  configFn =
    { config, pkgs, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      home-manager.users.${user}.home.packages = with pkgs; [
        swaybg
        hyprpicker
        wl-gammactl
      ];
    };
} args
