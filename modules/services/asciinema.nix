{
  lib,
  pkgs,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) dataRoot;
  username = config.sinnix.user.name;
  recordingsDir = "${dataRoot}/asciinema_recording";
in
{
  config = {
    environment.systemPackages = lib.mkAfter [ pkgs.asciinema_3 ];

    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${recordingsDir} 0755 ${username} users -"
    ];
  };
}
