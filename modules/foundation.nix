# Unified System Foundation and Project Topology
#
# Provides:
# - Primary user and machine identity
# - Global filesystem paths and realm topology
# - Project constellation mapping and environment variables
# - System-wide localization (time, locale, console)
{
  lib,
  pkgs,
  config,
  ...
}:
let
  inherit (lib) types mkOption mkIf;
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
            librariesRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/libraries";
            };
            mediaRoot = mkOption {
              type = types.str;
              default = "${config.librariesRoot}/media";
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
            lynchpinExported = mkOption {
              type = types.str;
              default = "${config.root}/__lynchpin_exported";
              description = "Lynchpin's derived artifacts (ledgers, dashboards, repo-artefacts) — extracted from knowledgebase in 2026-04.";
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

    storage.nextcloudUser = mkOption {
      type = types.str;
      default = "michal";
      description = "WebDAV username on the Nextcloud server (may differ from system user).";
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
