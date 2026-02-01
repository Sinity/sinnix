{ mkFeatureModule, pkgs, helpers, ... }@args:
mkFeatureModule {
  path = [ "desktop" "theming" ];
  description = "Desktop theming (GTK/Qt overrides)";
  configFn =
    { config, lib, pkgs, helpers, user, ... }:
    let
      kvantumPkg =
        if lib.hasAttrByPath [ "qt6Packages" "qtstyleplugin-kvantum" ] pkgs then
          pkgs.qt6Packages.qtstyleplugin-kvantum
        else if lib.hasAttrByPath [ "libsForQt5" "kvantum" ] pkgs then
          pkgs.libsForQt5.kvantum
        else
          null;
    in
    {
      home-manager.users.${user} =
        { pkgs, lib, config, sinnix, ... }:
        let
          mkDotsFile = helpers.mkDotsFile sinnix config;
        in
        {
          gtk = {
            enable = true;
            iconTheme = {
              package = pkgs.papirus-icon-theme;
              name = "Papirus-Dark";
            };
          };

          qt = {
            enable = true;
            platformTheme.name = "qtct";
            style = {
              name = "kvantum";
            }
            // lib.optionalAttrs (kvantumPkg != null) {
              package = kvantumPkg;
            };
          };

          stylix.targets.qt.enable = false;

          home.activation.cleanupKvantum = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
            rm -rf "$HOME/.config/Kvantum"
          '';

          xdg.configFile = {
            "qt5ct/qt5ct.conf".source = mkDotsFile "/qt5ct/qt5ct.conf";
            "qt6ct/qt6ct.conf".source = mkDotsFile "/qt6ct/qt6ct.conf";
            "Kvantum".source = mkDotsFile "/Kvantum";
          };
        };
    };
} args
