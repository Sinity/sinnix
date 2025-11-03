{ lib, pkgs, config, ... }:
let
  inherit (config.sinnix.paths) torrentInbox outerRealm;
  username = config.sinnix.user.name;
in
{
  services.transmission = {
    enable = true;
    openFirewall = false;
    package = pkgs.transmission_4;
    user = username;
    group = "users";
    settings = {
      script-torrent-done-enabled = false;
      ratio-limit-enabled = false;
      umask = 18;
      download-dir = torrentInbox;
      incomplete-dir-enabled = false;
      rpc-enabled = false;
    };
  };

  systemd.tmpfiles.rules = lib.mkAfter [
    "d ${torrentInbox} 2775 ${username} users -"
  ];

  systemd.services.transmission.unitConfig.RequiresMountsFor =
    let
      needs = lib.unique [ torrentInbox outerRealm ];
    in
    needs;
}
