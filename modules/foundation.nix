# Unified System Foundation and Project Topology
#
# Primary user and machine identity, global filesystem paths and realm
# topology, project constellation mapping, and system-wide localization.
{
  lib,
  pkgs,
  config,
  ...
}:
let
  inherit (lib) types mkOption;
  cfg = config.sinnix;
in
{
  options.sinnix = {
    user.name = mkOption {
      type = types.str;
      default = "sinity";
      description = "Primary local user account name.";
    };

    machine.isDesktop = mkOption {
      type = types.bool;
      default = true;
      description = "Whether this host runs the desktop stack.";
    };

    paths = mkOption {
      type = types.submodule (
        { config, ... }:
        {
          options = {
            realmRoot = mkOption {
              type = types.str;
              default = "/realm";
            };
            dataRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/data";
            };
            capturesRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/captures";
            };
            exportsRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/exports";
            };
            selfRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/self";
              description = "Personal-identity records: genome, finance, private, code-archives, photos. Distinct from mediaRoot/books, which holds curated reference material, not records about the operator.";
            };
            mediaRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/media";
            };
            stateRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/state";
            };
            stagingRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/staging";
            };
            outerRealm = mkOption {
              type = types.str;
              default = "/outer-realm";
            };
            neoOuterRealm = mkOption {
              type = types.str;
              default = "/neo-outer-realm";
            };
            torrentInbox = mkOption {
              type = types.str;
              default = "${config.neoOuterRealm}/inbox";
            };
            projectRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/project/sinnix";
            };
            dotsRoot = mkOption {
              type = types.str;
              default = "${config.projectRoot}/dots";
            };
            cryptoRoot = mkOption {
              type = types.str;
              default = "/monero";
            };
          };
        }
      );
      default = { };
    };

    projects = mkOption {
      type = types.submodule (
        { config, ... }:
        {
          options = {
            root = mkOption {
              type = types.str;
              default = "/realm/project";
            };
            lynchpin = mkOption {
              type = types.str;
              default = "${config.root}/sinity-lynchpin";
            };
            sinex = mkOption {
              type = types.str;
              default = "${config.root}/sinex";
            };
            polylogue = mkOption {
              type = types.str;
              default = "${config.root}/polylogue";
            };
            sinnix = mkOption {
              type = types.str;
              default = "${config.root}/sinnix";
            };
            scribeTap = mkOption {
              type = types.str;
              default = "${config.root}/scribe-tap";
            };
            interceptBounce = mkOption {
              type = types.str;
              default = "${config.root}/intercept-bounce";
            };
            knowledgeExtract = mkOption {
              type = types.str;
              default = "${config.root}/knowledge-extract";
            };
            knowledgebase = mkOption {
              type = types.str;
              default = "/realm/data/knowledgebase";
            };
            entries = mkOption {
              type = types.attrsOf (
                types.submodule {
                  options = {
                    path = mkOption { type = types.str; };
                    remote = mkOption {
                      type = types.nullOr types.str;
                      default = null;
                    };
                    defaultRef = mkOption {
                      type = types.str;
                      default = "master";
                    };
                    remoteRead = mkOption {
                      type = types.bool;
                      default = false;
                    };
                    remoteWrite = mkOption {
                      type = types.bool;
                      default = false;
                    };
                  };
                }
              );
              readOnly = true;
              default = {
                sinnix = {
                  path = config.sinnix;
                  remote = "https://github.com/Sinity/sinnix.git";
                  remoteRead = true;
                  remoteWrite = true;
                };
                sinex = {
                  path = config.sinex;
                  remote = "https://github.com/Sinity/sinex.git";
                  remoteRead = true;
                  remoteWrite = true;
                };
                polylogue = {
                  path = config.polylogue;
                  remote = "https://github.com/Sinity/polylogue.git";
                  remoteRead = true;
                  remoteWrite = true;
                };
                lynchpin = {
                  path = config.lynchpin;
                  remote = "https://github.com/Sinity/sinity-lynchpin.git";
                  remoteRead = true;
                  remoteWrite = true;
                };
              };
              description = "Canonical project metadata consumed by agent and evidence surfaces.";
            };
            lynchpinExported = mkOption {
              type = types.str;
              default = "${config.root}/__lynchpin_exported";
              description = "Lynchpin's derived artifacts (ledgers, dashboards, repo-artefacts), separate from knowledgebase.";
            };
            pwrank = mkOption {
              type = types.str;
              default = "${config.root}/pwrank";
            };
          };
        }
      );
      default = { };
    };

  };

  config = {
    # Localization
    time.timeZone = "Europe/Warsaw";
    i18n = {
      defaultLocale = "en_US.UTF-8";
      extraLocaleSettings = lib.genAttrs [
        "LC_ADDRESS"
        "LC_IDENTIFICATION"
        "LC_MEASUREMENT"
        "LC_MONETARY"
        "LC_NAME"
        "LC_NUMERIC"
        "LC_PAPER"
        "LC_TELEPHONE"
        "LC_TIME"
      ] (_: "pl_PL.UTF-8");
    };
    console = {
      earlySetup = true;
      keyMap = "pl2";
      font = "ter-220n";
      packages = [ pkgs.terminus_font ];
    };

    # User definition
    users.mutableUsers = false;
    users.groups.${cfg.user.name} = { };
    users.users.${cfg.user.name} = {
      isNormalUser = true;
      group = cfg.user.name;
      extraGroups = [
        "networkmanager"
        "wheel"
        "users"
        "seat"
        "video"
        "fuse"
      ];
      shell = pkgs.zsh;
      hashedPasswordFile = config.sinnix.secrets.paths."${cfg.user.name}-password";
    };
    users.users.root = {
      shell = pkgs.zsh;
      hashedPasswordFile = config.sinnix.secrets.paths.root-password;
    };

    # Global environment exports
    environment.variables = {
      LYNCHPIN_REPO_ROOT = cfg.projects.lynchpin;
      SINEX_ROOT = cfg.projects.sinex;
      POLYLOGUE_ROOT = cfg.projects.polylogue;
      SINNIX_ROOT = cfg.projects.sinnix;
      KNOWLEDGEBASE_ROOT = cfg.projects.knowledgebase;
    };
  };
}
