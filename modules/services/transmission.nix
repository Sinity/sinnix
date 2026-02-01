# Transmission BitTorrent Client
#
# Downloads to torrentInbox, uses strict systemd hardening.
# RPC accessible only on localhost (no auth required).
{ mkServiceModule, lib, pkgs, ... }@args:
mkServiceModule {
  name = "transmission";
  description = "Transmission BitTorrent client";
  configFn = { config, lib, pkgs, cfg, ... }:
    let
      inherit (config.sinnix.paths) torrentInbox outerRealm;
      username = config.sinnix.user.name;
    in
    {
      services.transmission = {
        enable = true;
        openFirewall = true;
        package = pkgs.transmission_4;
        user = username;
        group = "users";
        settings = {
          script-torrent-done-enabled = false;
          ratio-limit-enabled = false;
          umask = 18;
          download-dir = torrentInbox;
          incomplete-dir-enabled = false;
          rpc-enabled = true;
          rpc-bind-address = "127.0.0.1";
          rpc-port = 9091;
          rpc-url = "/transmission/";
          # Auth disabled intentionally - RPC only accessible on localhost
          rpc-authentication-required = false;
          rpc-whitelist-enabled = false;
          rpc-host-whitelist = "127.0.0.1,localhost";
        };
      };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${torrentInbox} 2775 ${username} users -"
      ];

      systemd.services.transmission = {
        unitConfig.RequiresMountsFor = lib.unique [
          torrentInbox
          outerRealm
        ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = lib.mkMerge [
          (lib.sinnix.systemd.mkHardenedService {
            level = "strict";
            readWritePaths = [ torrentInbox "/var/lib/transmission" ];
          })
          (lib.sinnix.systemd.mkRestartPolicy { strategy = "on-failure"; delaySec = 10; })
        ];
      };
    };
} args
