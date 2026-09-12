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
            activityRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/activity";
              description = "Personal activity records: app focus, terminal, media playback, notifications, browsing, messages, transcripts, and ranking sessions.";
            };
            machineRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/machine";
              description = "Host/device telemetry: machine-telemetry, syslog, netflow, router, monitor DDC, audio device/topology streams, the phone app's own lane.";
            };
            healthRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/health";
              description = "Health records, measurements, genome data, and therapy material.";
            };
            journalRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/journal";
              description = "The operator journal and its historical entries.";
            };
            documentsRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/documents";
              description = "Personal documents, including finance, career, insurance and device records.";
            };
            photosRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/photos";
            };
            libraryRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library";
              description = "Books, media, reference datasets, models, packaged code, and game libraries.";
            };
            datasetsRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library/datasets";
              description = "Third-party reference corpora acquired for compute (reddit dumps, hf-datasets): re-acquirable, ownership='others'.";
            };
            modelsRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library/models";
              description = "Model weights used by workstation services and analysis tools.";
            };
            stateRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/state";
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
            privateCatalogFile = mkOption {
              type = types.str;
              default = cfg.secrets.paths.private-project-catalog;
              description = "Optional runtime catalog for projects whose metadata is not tracked publicly.";
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
                    observerRead = mkOption {
                      type = types.bool;
                      default = false;
                    };
                    agentctl = mkOption {
                      type = types.bool;
                      default = true;
                      description = "Whether this repository supplies an agentctl project descriptor.";
                    };
                    checkoutDiscovery = mkOption {
                      type = types.enum [ "git-worktree" ];
                      default = "git-worktree";
                      description = "Declared owner used to enumerate code checkouts.";
                    };
                    devtoolsEntrypoint = mkOption {
                      type = types.nullOr types.str;
                      default = null;
                      description = "Optional project-native development entrypoint.";
                    };
                    taskAuthority = mkOption {
                      type = types.nullOr (
                        types.submodule {
                          options = {
                            owner = mkOption {
                              type = types.enum [ "beads" ];
                              default = "beads";
                            };
                            workspace = mkOption { type = types.str; };
                            database = mkOption { type = types.str; };
                            projectUuid = mkOption {
                              type = types.nullOr types.str;
                              default = null;
                            };
                            publicationPolicy = mkOption {
                              type = types.enum [
                                "local"
                                "dolt-sync"
                              ];
                              default = "local";
                            };
                          };
                        }
                      );
                      default = null;
                      description = "Optional canonical Beads task authority for this project.";
                    };
                  };
                }
              );
              default = {
                sinnix = {
                  path = "${config.root}/sinnix";
                  remote = "https://github.com/Sinity/sinnix.git";
                  observerRead = true;
                  devtoolsEntrypoint = "nix develop";
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/sinnix/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/sinnix/.beads/dolt";
                    publicationPolicy = "dolt-sync";
                  };
                };
                sinex = {
                  path = "${config.root}/sinex";
                  remote = "https://github.com/Sinity/sinex.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/sinex/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/sinex/.beads/dolt";
                    publicationPolicy = "dolt-sync";
                  };
                };
                polylogue = {
                  path = "${config.root}/polylogue";
                  remote = "https://github.com/Sinity/polylogue.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/polylogue/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/polylogue/.beads/dolt";
                    publicationPolicy = "dolt-sync";
                  };
                };
                lynchpin = {
                  path = "${config.root}/sinity-lynchpin";
                  remote = "https://github.com/Sinity/sinity-lynchpin.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/lynchpin/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/lynchpin/.beads/dolt";
                    publicationPolicy = "local";
                  };
                };
              };
              description = "Public project metadata consumed by agent and evidence surfaces.";
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
      # Fixed so units may name the user runtime directory (/run/user/<uid>).
      uid = 1000;
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
      LYNCHPIN_REPO_ROOT = cfg.projects.entries.lynchpin.path;
      SINEX_ROOT = cfg.projects.entries.sinex.path;
      POLYLOGUE_ROOT = cfg.projects.entries.polylogue.path;
      # Verification run history is the one polylogue artifact that outlives a
      # checkout, so it belongs in the data lake rather than per-checkout state.
      # Every worktree and lane inherits this, which is what makes cross-lane
      # comparison possible at all.
      POLYLOGUE_VERIFY_HISTORY_PATH = "/realm/activity/dev/polylogue/verify-history.jsonl";
      SINNIX_ROOT = cfg.projects.entries.sinnix.path;
      RAWLOG_FILE = "${cfg.paths.journalRoot}/raw-log.md";
    };
  };
}
