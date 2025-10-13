{ ... }:
{
  services.transmission = {
    enable = true;
    openFirewall = false;
    settings = {
      script-torrent-done-enabled = false;
      ratio-limit-enabled = false;
      umask = 18;
      download-dir = "/outer-realm/inbox";
      incomplete-dir-enabled = false;
      rpc-enabled = true;
      rpc-bind-address = "127.0.0.1";
      rpc-port = 9091;
      rpc-authentication-required = false;
    };
  };
}
