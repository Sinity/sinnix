# Private phone-media ingress over the tailnet.
#
# The endpoint starts without peers because a freshly installed Android client
# does not have a device ID until its first launch. Pairing is initially
# mutable; once the Redmi ID and folder IDs are known, they belong here as
# declarative devices/folders and the override switches can be tightened.
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

        # Keep the bootstrap configuration added through the local REST/UI
        # until the phone's generated device identity is known. The completed
        # pairing is then promoted into this module.
        overrideDevices = false;
        overrideFolders = false;
        settings.options = {
          globalAnnounceEnabled = false;
          localAnnounceEnabled = false;
          relaysEnabled = false;
          urAccepted = -1;
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
