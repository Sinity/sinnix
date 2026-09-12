{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "xr"
  ];
  description = "PC VR streaming and headset management";
  subFeatures = {
    alvr = {
      description = "ALVR SteamVR streaming dashboard";
      default = true;
    };
    wivrn = {
      description = "WiVRn OpenXR streaming dashboard and LAN discovery";
      default = true;
    };
    sidequest = {
      description = "SideQuest headset application manager";
      default = true;
    };
    kdeconnect = {
      description = "KDE Connect LAN companion for headset file and input utilities";
      default = true;
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      cfg,
      user,
      ...
    }:
    let
      lanInterface = "enp4s0";
    in
    lib.mkMerge [
      {
        # Keep OpenXR runtime choice out of the ambient desktop environment:
        # WiVRn and SteamVR select it for their own launched session.
        home-manager.users.${user}.home.packages = with pkgs; [
          monado
          opencomposite
        ];
      }
      (lib.mkIf cfg.alvr.enable {
        home-manager.users.${user}.home.packages = [ pkgs.alvr ];
        # The streamer only listens while its dashboard/session is launched.
        networking.firewall.interfaces.${lanInterface} = {
          allowedTCPPorts = [ 9943 9944 ];
          allowedUDPPorts = [ 9943 9944 ];
        };
      })
      (lib.mkIf cfg.wivrn.enable {
        home-manager.users.${user}.home.packages = [ pkgs.wivrn ];
        services.avahi = {
          enable = true;
          nssmdns4 = true;
          openFirewall = true;
          publish = {
            enable = true;
            userServices = true;
          };
        };
        networking.firewall.interfaces.${lanInterface} = {
          allowedTCPPorts = [ 9757 ];
          allowedUDPPorts = [ 9757 ];
        };
      })
      (lib.mkIf cfg.sidequest.enable {
        home-manager.users.${user}.home.packages = [ pkgs.sidequest ];
      })
      (lib.mkIf cfg.kdeconnect.enable {
        programs.kdeconnect.enable = true;
        # KDE Connect discovers and transports only on the local physical LAN.
        networking.firewall.interfaces.${lanInterface} = {
          allowedTCPPortRanges = [
            {
              from = 1714;
              to = 1764;
            }
          ];
          allowedUDPPortRanges = [
            {
              from = 1714;
              to = 1764;
            }
          ];
        };
      })
    ];
} args
