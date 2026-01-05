{
  lib,
  ...
}:
let
  inherit (lib) types mkOption;
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

    machine = {
      isDesktop = mkOption {
        type = types.bool;
        default = true;
        description = "Whether this host runs the desktop stack (Hyprland, Mullvad, Transmission, etc.).";
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

            capturesRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/captures";
              description = "Root directory for continuous/local telemetry captures.";
            };

            exportsRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/exports";
              description = "Root directory for provider exports (GDPR/Takeout/etc.).";
            };

            librariesRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/libraries";
              description = "Root directory for curated long-lived libraries.";
            };

            indicesRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/indices";
              description = "Root directory for service indexes and derived stores (qdrant, sinevec, etc.).";
            };

            mediaRoot = mkOption {
              type = types.str;
              default = "${config.librariesRoot}/media";
              description = "Directory storing primary media libraries for desktop-managed media workflows.";
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

            projectRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/sinnix";
              description = "Location of the Sinnix git checkout used for editable dotfiles and dev helpers.";
            };

            dotsRoot = mkOption {
              type = types.str;
              default = "${config.projectRoot}/dots";
              description = "Directory containing tracked dotfiles that should be symlinked into $HOME.";
            };
          };
        }
      );
      default = { };
      description = "Filesystem roots that multiple modules share.";
    };
  };

}
