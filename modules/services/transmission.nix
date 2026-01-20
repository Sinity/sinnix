{
  lib,
  pkgs,
  config,
  ...
}:
let
  cfg = config.sinnix.services.transmission;
  inherit (config.sinnix.paths) torrentInbox outerRealm;
  username = config.sinnix.user.name;
in
{
  options.sinnix.services.transmission = {
    enable = lib.mkEnableOption "Transmission BitTorrent client";
  };

  config = lib.mkIf cfg.enable {
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
        # Auth disabled intentionally - RPC only accessible on localhost (127.0.0.1)
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
      # Ensure network is ready and add restart policy
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      serviceConfig = {
        Restart = "on-failure";
        RestartSec = 10;
        # Systemd hardening
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictRealtime = true;
        LockPersonality = true;
        # Allow write to download directories
        ReadWritePaths = [
          torrentInbox
          "/var/lib/transmission"
        ];
      };
    };
  };
}
