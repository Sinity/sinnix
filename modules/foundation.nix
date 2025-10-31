{
  lib,
  ...
}:
let
  inherit (lib) types mkOption mkDefault mkIf;
in
{
  options.sinnix = {
    user = {
      name = mkOption {
        type = types.str;
        default = "sinity";
        description = ''
          Primary local user account name that Sinnix modules assume when
          wiring permissions, tmpfiles rules, and service ACLs.
        '';
      };
    };

    paths = mkOption {
      type = types.submodule (
        { config, ... }:
        {
          options = {
            realmRoot = mkOption {
              type = types.str;
              default = "/realm";
              description = "Top-level directory containing long-lived realm data and metadata.";
            };

            dataRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/data";
              description = "Root directory for durable datasets (photos, vector indexes, etc.).";
            };

            mediaRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/media";
              description = "Directory storing primary media libraries managed by photoprism and similar services.";
            };

            outerRealm = mkOption {
              type = types.str;
              default = "/outer-realm";
              description = "External storage mount used for large artefacts (e.g. transmission downloads).";
            };

            torrentInbox = mkOption {
              type = types.str;
              default = "${config.outerRealm}/inbox";
              description = "Download directory for transmission and other ingest pipelines.";
            };
          };
        }
      );
      default = { };
      description = "Filesystem roots that multiple modules share.";
    };
  };

}
