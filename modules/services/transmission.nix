{ lib, config, ... }:
let
  torrentInbox = config.sinnix.paths.torrentInbox;
  username = config.sinnix.user.name;
in
{
  services.transmission = {
    enable = true;
    openFirewall = false;
    settings = {
      script-torrent-done-enabled = false;
      ratio-limit-enabled = false;
      umask = 18;
      download-dir = torrentInbox;
      incomplete-dir-enabled = false;
      rpc-enabled = true;
      rpc-bind-address = "127.0.0.1";
      rpc-port = 9091;
      rpc-authentication-required = false;
    };
  };

  systemd.tmpfiles.rules = lib.mkAfter [
    "d ${torrentInbox} 2775 ${username} users -"
  ];
}
