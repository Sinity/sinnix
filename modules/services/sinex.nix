{
  config,
  lib,
  pkgs,
  ...
}:
let
  inherit (config.sinnix.paths) dataRoot realmRoot;
in
{
  config = {
    systemd.services."sinex-blob-init".path = [ pkgs.git pkgs.git-annex ];

    services.sinex = {
      enable = false;
      users.target = config.sinnix.user.name;

      database.autoSetup = true;
      logLevel = "debug";
      storage.blob.enable = true;
      storage.dlq.enable = true;
      shell.asciinema.autoRecord = true;

      stateRoot = "${dataRoot}/sinex";
      satellites.filesystem.watchPaths = [ realmRoot ];
      # satellites.defaults.instances = 2; # I want to test whether these mechanisms work first
    };
  };
}
