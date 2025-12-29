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
        rpc-authentication-required = false;
        rpc-whitelist-enabled = false;
        rpc-host-whitelist = "127.0.0.1,localhost";
      };
    };

    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${torrentInbox} 2775 ${username} users -"
    ];

    systemd.services.transmission.unitConfig.RequiresMountsFor =
      let
        needs = lib.unique [
          torrentInbox
          outerRealm
        ];
      in
      needs;
  };
}
