# Transmission BitTorrent Client
#
# Downloads to torrentInbox, uses strict systemd hardening.
# RPC accessible only on localhost (no auth required).
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "transmission";
  description = "Transmission BitTorrent client";
  health = {
    unit = "transmission.service";
    type = "service";
    restartable = true;
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    let
      inherit (config.sinnix.paths) torrentInbox neoOuterRealm;
      username = config.sinnix.user.name;
      neoOuterRealmMount = "neo\\x2douter\\x2drealm.mount";
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
        wantedBy = lib.mkForce [ ];
        unitConfig.RequiresMountsFor = lib.unique [
          torrentInbox
          neoOuterRealm
        ];
        unitConfig.PartOf = [ neoOuterRealmMount ];
        after = [
          "network-online.target"
          neoOuterRealmMount
        ];
        wants = [ "network-online.target" ];
        serviceConfig = lib.mkMerge [
          (lib.sinnix.systemd.mkHardenedService {
            level = "strict";
            readWritePaths = [
              torrentInbox
              "/var/lib/transmission"
            ];
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 10;
          })
        ];
      };

      systemd.services.transmission-autostart = {
        description = "Start Transmission after boot settles";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          Restart = "on-failure";
          RestartSec = "30s";
          ExecStart = pkgs.writeShellScript "transmission-autostart" ''
            set -euo pipefail

            if ${pkgs.systemd}/bin/systemctl is-active --quiet transmission.service; then
              exit 0
            fi

            exec ${pkgs.systemd}/bin/systemctl start transmission.service
          '';
        };
      };

      systemd.timers.transmission-autostart = {
        description = "Deferred Transmission startup";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "30s";
          Unit = "transmission-autostart.service";
        };
      };
    };
} args
