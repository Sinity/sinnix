{
  lib,
  pkgs,
  config,
  ...
}:
let
  cfg = config.sinnix.services.asciinema;
  inherit (config.sinnix.paths) capturesRoot;
  username = config.sinnix.user.name;
  recordingsDir = "${capturesRoot}/asciinema";
in
{
  options.sinnix.services.asciinema = {
    enable = lib.mkEnableOption "Asciinema terminal recorder";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = lib.mkAfter [ pkgs.asciinema_3 ];

    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${recordingsDir} 0755 ${username} users -"
    ];
  };
}
