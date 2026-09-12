# Private mobile-media ingress over the tailnet or an explicitly forwarded
# local transport.
#
# Mobile devices remain authoritative for media. Prime receives recoverable
# mirrors; staggered versions protect against accidental deletion at source.
{
  mkServiceModule,
  lib,
  ...
}@args:
mkServiceModule {
  name = "syncthing-media";
  description = "Syncthing endpoint for private phone-media ingress";
  surface = {
    unit = "syncthing.service";
    resourceClass = "background";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { config, ... }:
    let
      username = config.sinnix.user.name;
      stateDir = "/realm/state/syncthing";
      mediaDir = "/realm/photos/phone-sync";
      questMediaDir = "/realm/photos/quest-3/videoshots";
    in
    {
      services.syncthing = {
        enable = true;
        user = username;
        group = "users";
        dataDir = mediaDir;
        configDir = "${stateDir}/config";
        databaseDir = "${stateDir}/database";
        guiAddress = "127.0.0.1:8384";
        openDefaultPorts = false;

        overrideDevices = true;
        overrideFolders = true;
        settings = {
          devices.redmi-note-11 = {
            id = "AKGRD25-3B56PTM-ANHPZ4B-HFL7VWF-QDP3OOJ-HSSWVBK-6XAZPRQ-5PVOZQY";
            addresses = [
              "tcp://100.111.240.107:22000"
              "quic://100.111.240.107:22000"
            ];
          };
          devices.quest-3 = {
            id = "ZB4K2DB-SXJRE2T-CCVTEAZ-HHQLNJ5-T2UJLZB-CZ2I5A6-QPK5NJ5-G2GFGAO";
            # Quest initiates the connection through `adb reverse`; it has no
            # independently reachable address that the host should probe.
            addresses = [ "dynamic" ];
          };

          folders =
            lib.genAttrs [ "DCIM" "Pictures" "Movies" ] (name: {
              id = "redmi-${lib.toLower name}";
              path = "${mediaDir}/${name}";
              devices = [ "redmi-note-11" ];
              type = "receiveonly";
              versioning = {
                type = "staggered";
                params = {
                  cleanInterval = "3600";
                  maxAge = "31536000";
                };
              };
            })
            // {
              quest-videoshots = {
                id = "quest-videoshots";
                label = "Quest 3 Videoshots";
                path = questMediaDir;
                devices = [ "quest-3" ];
                type = "receiveonly";
                versioning = {
                  type = "staggered";
                  params = {
                    cleanInterval = "3600";
                    maxAge = "31536000";
                  };
                };
              };
            };

          options = {
            globalAnnounceEnabled = false;
            localAnnounceEnabled = false;
            relaysEnabled = false;
            # Peers use explicit tailnet addresses.  Do not probe or request
            # router port mappings for a service intentionally confined there.
            natEnabled = false;
            urAccepted = -1;
          };
        };
      };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${stateDir} 0750 ${username} users -"
        "d ${stateDir}/config 0700 ${username} users -"
        "d ${stateDir}/database 0700 ${username} users -"
        "d ${mediaDir} 0750 ${username} users -"
        "d ${questMediaDir} 0750 ${username} users -"
      ];

      # Data transfer and QUIC are admitted only from tailnet peers. The web
      # UI remains loopback-only and is never exposed by this module.
      networking.firewall.interfaces.tailscale0 = {
        allowedTCPPorts = [ 22000 ];
        allowedUDPPorts = [ 22000 ];
      };
    };
} args
