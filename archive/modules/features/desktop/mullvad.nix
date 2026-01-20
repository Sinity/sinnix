{ pkgs, lib, mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [ "desktop" "mullvad" ];
  description = "Mullvad VPN daemon and userland tooling";
  configFn =
    { config, pkgs, ... }:
    let
      user = config.sinnix.user.name;
    in
    {
      services.mullvad-vpn.enable = true;

      environment.systemPackages = lib.mkAfter [ pkgs.mullvad-vpn ];

      home-manager.users.${user} = { ... }: {
        programs.mullvad-vpn = {
          enable = true;
          settings = {
            preferredLocale = "system";
            autoConnect = false;
            enableSystemNotifications = true;
            monochromaticIcon = false;
            startMinimized = true;
            unpinnedWindow = true;
            browsedForSplitTunnelingApplications = [ ];
            changelogDisplayedForVersion = "2025.2";
            animateMap = true;
          };
        };

        xdg.configFile."autostart/mullvad-vpn.desktop".text = ''
          [Desktop Entry]
          Type=Application
          Name=Mullvad VPN (disabled)
          Hidden=true
        '';
      };
    };
} args
