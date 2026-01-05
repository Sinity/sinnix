{
  config,
  pkgs,
  lib,
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.sinex;
  inherit (config.sinnix.paths) indicesRoot realmRoot;
  dbProvision = cfg.enable || cfg.provisionDatabase;
  sinexPkgs = inputs.sinex.packages.${pkgs.stdenv.hostPlatform.system};
in
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    provisionDatabase = lib.mkEnableOption "Provision the Sinex PostgreSQL database without running services";
  };

  config = lib.mkIf (config.services ? sinex) (lib.mkMerge [
    {
      services.sinex.package = lib.mkDefault sinexPkgs.sinex;
      services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexCli;

      services.sinex.enable = lib.mkDefault cfg.enable;
      services.sinex.core.enable = lib.mkDefault cfg.enable;
      services.sinex.database.enable = lib.mkDefault dbProvision;
      services.sinex.database.autoSetup = lib.mkDefault dbProvision;
      services.sinex.nats.enable = lib.mkDefault cfg.enable;
      services.sinex.storage.blob.enable = lib.mkDefault cfg.enable;
      services.sinex.storage.dlq.enable = lib.mkDefault cfg.enable;
      services.sinex.lifecycle.maintenance.enable = lib.mkDefault cfg.enable;
    }

    (lib.mkIf cfg.enable {
      systemd.services."sinex-blob-init".path = [
        pkgs.git
        pkgs.git-annex
      ];

      services.sinex = {
        enable = true;
        users.target = config.sinnix.user.name;

        database.autoSetup = true;
        logLevel = "debug";
        storage.blob.enable = true;
        storage.dlq.enable = true;
        shell.asciinema.autoRecord = true;

        stateRoot = "${indicesRoot}/sinex";
        satellites.filesystem.watchPaths = [ realmRoot ];
        # satellites.defaults.instances = 2; # I want to test whether these mechanisms work first
      };
    })
  ]);
}
