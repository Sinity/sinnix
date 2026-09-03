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
            activityRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/activity";
              description = "Ambient personal-activity capture: input devices, window/app focus, terminal, media playback, notifications, URL visits, IRC, mail, calendar, transcripts, ranking sessions. Sole home for capture lanes about the operator (captures/ and comms/ retired 2026-08-24; a new lane lands here or in machineRoot/healthRoot by subject).";
            };
            machineRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/machine";
              description = "Host/device telemetry: machine-telemetry, syslog, netflow, router, monitor DDC, audio device/topology streams, the phone app's own lane.";
            };
            healthRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/health";
              description = "Body/environment physiology: Awair air quality (as health/environment), Xiaomi cloud health witness, phone health/battery/thermal.";
            };
            aiRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/ai";
              description = "AI chat/dialogue archives and analyses, including the live polylogue capture lane.";
            };
            selfRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/self";
              description = "Personal-identity records: genome, finance, private, code-archives, photos. Distinct from mediaRoot/books, which holds curated reference material, not records about the operator.";
            };
            mediaRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library/media";
              description = "Consumption media: Steam, books, videos, substack, wallpaper, edu, stashbox. Re-acquirable, ownership='others' -- was /realm/media until the library/ recut (2026-08-17); everything under it is loss-tolerant the same way libraryRoot as a whole is.";
            };
            datasetsRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library/datasets";
              description = "Third-party reference corpora acquired for compute (reddit dumps, hf-datasets): re-acquirable, ownership='others'.";
            };
            modelsRoot = mkOption {
              type = types.str;
              default = "${config.realmRoot}/library/models";
              description = "Model weights (ollama, gguf, embeddings, sherpa, tts, whisper, ...): re-acquirable, ownership='others'. Was mediaRoot/model until the library/ recut split it out with its own root, since it was previously a subdirectory of media rather than a peer.";
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
                    observerRead = mkOption {
                      type = types.bool;
                      default = false;
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
              readOnly = true;
              default = {
                sinnix = {
                  path = config.sinnix;
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
                  path = config.sinex;
                  remote = "https://github.com/Sinity/sinex.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/sinex/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/sinex/.beads/dolt";
                    publicationPolicy = "dolt-sync";
                  };
                };
                polylogue = {
                  path = config.polylogue;
                  remote = "https://github.com/Sinity/polylogue.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/polylogue/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/polylogue/.beads/dolt";
                    publicationPolicy = "dolt-sync";
                  };
                };
                lynchpin = {
                  path = config.lynchpin;
                  remote = "https://github.com/Sinity/sinity-lynchpin.git";
                  observerRead = true;
                  taskAuthority = {
                    workspace = "${cfg.paths.stateRoot}/tasks/lynchpin/.beads";
                    database = "${cfg.paths.stateRoot}/tasks/lynchpin/.beads/dolt";
                    publicationPolicy = "local";
                  };
                };
              };
              description = "Canonical project metadata consumed by agent and evidence surfaces.";
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
      LYNCHPIN_REPO_ROOT = cfg.projects.lynchpin;
      SINEX_ROOT = cfg.projects.sinex;
      POLYLOGUE_ROOT = cfg.projects.polylogue;
      # Verification run history is the one polylogue artifact that outlives a
      # checkout, so it belongs in the data lake rather than per-checkout state.
      # Every worktree and lane inherits this, which is what makes cross-lane
      # comparison possible at all.
      POLYLOGUE_VERIFY_HISTORY_PATH = "/realm/data/activity/dev/polylogue/verify-history.jsonl";
      SINNIX_ROOT = cfg.projects.sinnix;
      KNOWLEDGEBASE_ROOT = cfg.projects.knowledgebase;
    };
  };
}
