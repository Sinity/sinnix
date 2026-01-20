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

  # Only configure if sinex module is available from the flake input
  config = lib.mkIf (config.services ? sinex) (lib.mkMerge [
    # Package defaults (always applied when module exists)
    {
      services.sinex.package = lib.mkDefault sinexPkgs.sinex;
      services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexCli;
    }

    # Database-only provisioning (for dev environments)
    (lib.mkIf dbProvision {
      services.sinex.database.enable = true;
      services.sinex.database.autoSetup = true;
    })

    # Full service configuration
    (lib.mkIf cfg.enable {
      systemd.services."sinex-blob-init" = {
        path = [
          pkgs.git
          pkgs.git-annex
        ];
        # Ensure database is ready before blob init
        after = [ "postgresql.service" ];
        requires = [ "postgresql.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
      };

      services.sinex = {
        enable = true;
        core.enable = true;
        nats.enable = true;
        storage.blob.enable = true;
        storage.dlq.enable = true;
        lifecycle.maintenance.enable = true;

        users.target = config.sinnix.user.name;
        logLevel = "debug";
        shell.asciinema.autoRecord = true;
        stateRoot = "${indicesRoot}/sinex";
        satellites.filesystem.watchPaths = [ realmRoot ];
      };
    })
  ]);
}
