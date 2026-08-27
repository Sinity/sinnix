# Private phone-media ingress over the tailnet.
#
# The Redmi is authoritative for media. Prime receives a recoverable mirror;
# staggered versions protect against accidental deletion on the phone.
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
    resourceClass = "background-maintenance";
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
      mediaDir = "/realm/data/self/photos/phone-sync";
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

          folders = lib.genAttrs [ "DCIM" "Pictures" "Movies" ] (name: {
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
          });

          options = {
            globalAnnounceEnabled = false;
            localAnnounceEnabled = false;
            relaysEnabled = false;
            urAccepted = -1;
          };
        };
      };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${stateDir} 0750 ${username} users -"
        "d ${stateDir}/config 0700 ${username} users -"
        "d ${stateDir}/database 0700 ${username} users -"
        "d ${mediaDir} 0750 ${username} users -"
      ];

      # Data transfer and QUIC are admitted only from tailnet peers. The web
      # UI remains loopback-only and is never exposed by this module.
      networking.firewall.interfaces.tailscale0 = {
        allowedTCPPorts = [ 22000 ];
        allowedUDPPorts = [ 22000 ];
      };
    };
} args
