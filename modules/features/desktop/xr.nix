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
  description = "PC VR, spatial desktop, and Quest management";
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
    desktop = {
      description = "WayVR spatial desktop and Sunshine/Moonlight fallback";
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
      helpers,
      ...
    }:
    let
      lanInterface = "enp4s0";
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    lib.mkMerge [
      {
        # Keep OpenXR runtime choice out of the ambient desktop environment:
        # WiVRn and SteamVR select it for their own launched session.
        home-manager.users.${user}.home.packages = with pkgs; [
          monado
          opencomposite
          wayvr
          xrizer
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
        services.wivrn = {
          enable = true;
          autoStart = false;
          openFirewall = false;
          steam.enable = true;
          steam.importOXRRuntimes = true;
        };
        services.avahi = {
          enable = true;
          nssmdns4 = true;
          openFirewall = false;
          publish = {
            enable = true;
            userServices = true;
          };
        };
        networking.firewall.interfaces.${lanInterface} = {
          allowedTCPPorts = [ 9757 ];
          allowedUDPPorts = [ 5353 9757 ];
        };
        # Archives are retained until a later realm backup receipt exists;
        # the script exits successfully when the USB headset is absent, so a
        # daily timer is safe on an unattended workstation.
        sinnix.runtime.surfaces.quest-media-prune = {
          unit = "sinnix-quest-media-prune.timer";
          manager = "user";
          kind = "timer";
          observe = {
            enable = true;
            restartable = false;
          };
        };
      })
      (lib.mkIf cfg.wivrn.enable (
        lib.sinnix.mkScheduledJob
          {
            inherit config;
            unitName = "sinnix-quest-media-prune";
            description = "Prune Quest recordings safely archived and backed up for 30 days";
            surface = config.sinnix.runtime.surfaces.quest-media-prune;
          }
          {
            manager = "user";
            resourceClass = "background-maintenance";
            script = ''
              if ${scriptPkgs.sinnix-quest}/bin/sinnix-quest doctor >/dev/null; then
                exec ${scriptPkgs.sinnix-quest}/bin/sinnix-quest media prune --apply
              fi
            '';
            timer = {
              onCalendar = "*-*-* 03:30:00";
              persistent = true;
              randomizedDelaySec = "20min";
              accuracySec = "5min";
              description = "Daily safe Quest recording retention pass";
            };
          }
      ))
      (lib.mkIf cfg.desktop.enable {
        services.sunshine = {
          enable = true;
          autoStart = false;
          openFirewall = false;
          settings = {
            capture = "wlr";
            encoder = "nvenc";
            nvenc_preset = 1;
          };
          # The desktop entry is deliberately minimal. Pairing and session
          # credentials remain Sunshine-owned mutable state, not Nix text.
          applications.apps = [
            {
              name = "Sinnix desktop";
              auto-detach = "true";
            }
          ];
        };
        # Sunshine dlopens NVENC at runtime. NixOS exposes the matched driver
        # libraries here rather than in the package closure.
        systemd.user.services.sunshine.environment.LD_LIBRARY_PATH = "/run/opengl-driver/lib";
        networking.firewall.interfaces.${lanInterface} = {
          # Sunshine's default base port is 47989. Keep Moonlight traffic on
          # the physical LAN instead of opening the service globally.
          allowedTCPPorts = [ 47984 47989 47990 48010 ];
          allowedUDPPorts = [ 47998 47999 48000 48002 48010 ];
        };
      })
      (lib.mkIf cfg.sidequest.enable {
        home-manager.users.${user}.home.packages = [ pkgs.sidequest ];
      })
      (lib.mkIf cfg.kdeconnect.enable {
        home-manager.users.${user}.home.packages = [ pkgs.kdePackages.kdeconnect-kde ];
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
