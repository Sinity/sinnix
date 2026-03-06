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
            runtimeRoot = mkOption {
              type = types.str;
              default = "${config.dataRoot}/runtime";
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
              default = "${config.root}/knowledgebase";
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

    storage.nextcloudHost = mkOption {
      type = types.str;
      default = "@@NEXTCLOUD_ADDRESS@@";
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
      keyMap = "pl2";
      font = "Lat2-Terminus16";
    };

    # Password safety net: if agenix fails to decrypt password secrets,
    # preserve the current working password from /etc/shadow instead of
    # leaving the user with no password (which would cause lockout).
    # Runs after agenixInstall, before users activation.
    system.activationScripts.passwordSafetyNet = {
      deps = [ "agenixInstall" ];
      text =
        let
          userPwFile = config.sinnix.secrets.paths."${cfg.user.name}-password";
          rootPwFile = config.sinnix.secrets.paths.root-password;
          username = cfg.user.name;
        in
        ''
          password_fallback() {
            local user="$1" target="$2"
            if [ ! -s "$target" ]; then
              echo "WARNING: agenix did not decrypt $target — extracting fallback from /etc/shadow" >&2
              current_hash=$(${pkgs.gawk}/bin/awk -F: -v u="$user" '$1==u {print $2}' /etc/shadow 2>/dev/null)
              if [ -n "$current_hash" ] && [ "$current_hash" != "!" ] && [ "$current_hash" != "*" ]; then
                echo "$current_hash" > "$target"
                chmod 0400 "$target"
                chown root:root "$target"
                echo "  → Preserved existing password for $user (agenix recovery)" >&2
              else
                echo "CRITICAL: No fallback password available for $user — system may be inaccessible!" >&2
              fi
            fi
          }
          password_fallback "${username}" "${userPwFile}"
          password_fallback "root" "${rootPwFile}"
        '';
    };

    # User definition
    users.mutableUsers = false;
    users.users.${cfg.user.name} = {
      isNormalUser = true;
      extraGroups = [
        "networkmanager"
        "wheel"
        "users"
        "seat"
        "video"
        "wireshark"
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
