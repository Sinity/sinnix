{ lib, config, ... }:
let
  cfg = config.sinnix.features.desktop.theming;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.theming = {
    enable = lib.mkEnableOption "Desktop Theming (GTK/Qt/Stylix)";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} =
      {
        pkgs,
        lib,
        config,
        dotsRepoPath,
        helpers,
        ...
      }:
      let
        kvantumPkg =
          if lib.hasAttrByPath [ "qt6Packages" "qtstyleplugin-kvantum" ] pkgs then
            pkgs.qt6Packages.qtstyleplugin-kvantum
          else if lib.hasAttrByPath [ "libsForQt5" "kvantum" ] pkgs then
            pkgs.libsForQt5.kvantum
          else
            null;
        mkDotsRepoLink = helpers.mkDotsSymlink config dotsRepoPath;
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
          platformTheme = {
            name = "qtct";
          };
          style = {
            name = "kvantum";
          }
          // lib.optionalAttrs (kvantumPkg != null) {
            package = kvantumPkg;
          };
        };

        # Disable stylix management for QT to allow manual override if needed
        stylix.targets.qt.enable = false;

        home.activation.cleanupKvantum = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
          rm -rf "$HOME/.config/Kvantum"
        '';

        xdg.configFile = {
          "qt5ct/qt5ct.conf".source = mkDotsRepoLink "/qt5ct/qt5ct.conf";
          "qt6ct/qt6ct.conf".source = mkDotsRepoLink "/qt6ct/qt6ct.conf";
          "Kvantum" = {
            source = mkDotsRepoLink "/Kvantum";
          };
        };
      };
  };
}
