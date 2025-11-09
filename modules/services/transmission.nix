{ lib, pkgs, config, ... }:
let
  inherit (config.sinnix.paths) torrentInbox outerRealm;
  username = config.sinnix.user.name;
  isDesktop = config.sinnix.machine.isDesktop;
in
lib.mkIf isDesktop {
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
      needs = lib.unique [ torrentInbox outerRealm ];
    in
    needs;
}
