# Persistence Mechanism — BTRFS Rollback Impermanence
#
# Root subvolume @ is deleted and recreated each boot (initrd in hosts/*/storage.nix).
# Before wiping, the state is snapshotted as a safety net (never auto-pruned).
#
# This module defines sinnix.persistence options that other modules use to declare
# their persistence needs colocated with their configuration. Declarations are
# collected and wired into the impermanence module automatically.
#
# To declare persistence from any module:
#   sinnix.persistence.system.directories = [ "/var/lib/myservice" ];
#   sinnix.persistence.home.directories = [ ".config/myapp" ];
#
# "Unclaimed" entries (no owning module yet) are declared below as defaults.
{ lib, config, ... }:
let
  username = config.sinnix.user.name;
  cfg = config.sinnix.persistence;
  dirType = with lib.types; listOf (either str attrs);
in
{
  options.sinnix.persistence = {
    enable = lib.mkEnableOption "BTRFS rollback impermanence — bind-mounts from /persist into ephemeral @";

    system = {
      directories = lib.mkOption {
        type = dirType;
        default = [ ];
        description = "System directories to persist via bind mount.";
      };
      files = lib.mkOption {
        type = with lib.types; listOf str;
        default = [ ];
        description = "System files to persist via bind mount.";
      };
    };

    home = {
      directories = lib.mkOption {
        type = dirType;
        default = [ ];
        description = "Home directories to persist via bind mount.";
      };
      files = lib.mkOption {
        type = with lib.types; listOf str;
        default = [ ];
        description = "Home files to persist via bind mount.";
      };
    };

    # Early-boot placeholders for files that must exist before impermanence activates.
    # Defaults to persisted system files (machine-id, adjtime need to exist for systemd).
    initrdScaffold = {
      files = lib.mkOption {
        type = with lib.types; listOf str;
        default = [ ];
        description = "Files to touch in initrd before systemd starts.";
      };
      directories = lib.mkOption {
        type = with lib.types; listOf str;
        default = [ ];
        description = "Directories to mkdir in initrd before systemd starts.";
      };
    };
  };

  config = lib.mkIf cfg.enable {

    # ── Collector: wire all declarations into impermanence ───────────────
    environment.persistence."/persist" = {
      hideMounts = true;
      directories = cfg.system.directories;
      files = cfg.system.files;
    };
    environment.persistence."/persist".users.${username} = {
      directories = cfg.home.directories;
      files = cfg.home.files;
    };

    # Scaffold defaults: persisted system files + /var/log (for journal mount)
    sinnix.persistence.initrdScaffold = {
      files = lib.mkDefault cfg.system.files;
      directories = lib.mkDefault [ "/var/log" ];
    };

    # ── Core system state (no owning module) ────────────────────────────
    sinnix.persistence.system = {
      directories = [
        "/etc/ssh" # SSH host keys — agenix root of trust
        "/var/lib/bluetooth" # paired device keys
        "/var/lib/NetworkManager" # wired profiles, DHCP leases
        "/var/lib/nixos" # NixOS activation state
        "/var/lib/systemd" # timers, random-seed, rfkill, linger, timesync
        "/var/lib/sinex" # sinex event platform (→ services/sinex.nix)
        "/var/lib/transmission" # torrent state
        "/var/lib/tailscale" # auth keys and device identity
        "/var/lib/postgresql" # database files
        "/var/log/below" # below resource monitor
      ];
      files = [
        "/etc/machine-id" # dbus + journal continuity
        "/etc/adjtime" # hardware clock drift calibration
      ];
    };

    # ── Core home state (no owning module) ──────────────────────────────
    # AI tools and dev caches are colocated in features/dev/shell.nix.
    sinnix.persistence.home.directories = [
      # Secrets and credentials
      {
        directory = ".gnupg";
        mode = "0700";
      } # GPG keyring + git signing key
      ".ssh" # SSH identity keys
      {
        directory = ".config/gh";
        mode = "0700";
      } # GitHub CLI OAuth tokens
      {
        directory = ".config/rclone";
        mode = "0700";
      } # rclone remote credentials
      {
        directory = ".config/gcloud";
        mode = "0700";
      } # GCloud auth + credentials
      ".config/cachix" # cachix auth token
      {
        directory = ".config/io.datasette.llm";
        mode = "0700";
      } # LLM CLI keys + logs

      # Browsers
      {
        directory = ".config/google-chrome";
        mode = "0700";
      } # 1.6 GB profile
      {
        directory = ".config/spotify";
        mode = "0700";
      }
      {
        directory = ".config/ncspot";
        mode = "0700";
      }
      ".config/imgur-screenshot"
      {
        directory = ".config/qutebrowser";
        mode = "0700";
      }
      {
        directory = ".local/share/qutebrowser";
        mode = "0700";
      }

      # Telemetry (irreplaceable)
      ".local/share/atuin" # shell history DB, 97 MB
      ".local/share/activitywatch" # AW SQLite DB, 674 MB
      ".config/activitywatch" # AW watcher configs (runtime-written)
      ".config/awatcher" # awatcher config.toml

      # Task/time tracking
      ".config/task"
      ".task" # taskwarrior DB (TW3/taskchampion)
      ".config/timewarrior"
      ".local/share/timewarrior"

      # Large installs
      ".local/share/nvim" # Mason LSPs + treesitter, 1.6 GB
      {
        directory = ".local/share/Steam";
        mode = "0750";
      } # 65 GB game library

      # Nix user state
      ".cache/nix" # eval-cache-v6 + fetcher cache; keeps flake/direnv warm across rollbacks
      ".local/share/nix" # trusted-settings.json (cachix substituters)

      # UX state
      ".config/clipse" # clipboard history
      ".config/yazi" # file manager config (not HM managed)
      ".local/share/zoxide" # jump database
      ".local/share/direnv" # allowlist + env cache
      "wallpaper" # ~106 MB

      # IRC
      ".config/weechat"
      ".local/state/weechat"
      ".local/share/weechat" # logs

      # Peripherals
      {
        directory = ".config/kdeconnect";
        mode = "0700";
      } # device pairing certs
      ".config/solaar" # Logitech device config

      # Torrent
      {
        directory = ".config/transmission";
        mode = "0700";
      }

      # Polylogue
      {
        directory = ".config/polylogue";
        mode = "0700";
      } # OAuth credentials
      {
        directory = ".local/state/polylogue";
        mode = "0700";
      } # index, tokens, state
      ".local/share/polylogue" # conversation DB + drive-cache, ~61 GB

      # Large data
      ".local/share/hyprland" # Hyprland logs + state, ~1.1 GB
      ".local/share/gh" # GitHub CLI extensions, ~37 MB
    ];
  };
}
