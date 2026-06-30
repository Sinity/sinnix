# Borg backup target selector.
#
# Inert scaffolding for off-site backup destinations. Declares the
# `sinnix.services.borg.target` option without modifying the existing
# `modules/backup.nix` monolith (which is wired tightly for sinnix-prime
# local btrbk+borg). When a host opts into a non-local target, the
# resolved repo URI + auxiliary settings are exposed via
# `config.sinnix.services.borg.resolved.*` for downstream consumers
# (future ethereal-side borg jobs, or a refactor of backup.nix) to
# read.
#
# Default = local → zero behavior change on existing hosts.
{
  config,
  lib,
  ...
}:
let
  cfg = config.sinnix.services.borg;
  inherit (cfg) storagebox;
  resolvedRepo =
    {
      local = null;
      storagebox =
        if storagebox.account == "" then
          null
        else
          "ssh://${storagebox.account}@${storagebox.account}.your-storagebox.de:23/./${storagebox.path}";
      rclone-drive = "sftp://${cfg.rcloneDrive.host}:${toString cfg.rcloneDrive.port}/${cfg.rcloneDrive.path}";
    }
    .${cfg.target};
in
{
  options.sinnix.services.borg = {
    target = lib.mkOption {
      type = lib.types.enum [
        "local"
        "storagebox"
        "rclone-drive"
      ];
      default = "local";
      description = ''
        Destination class for borg archives.

        - `local`: file:// repos on a local mount (current sinnix-prime behavior).
        - `storagebox`: Hetzner Storage Box over SSH. Requires
          `sinnix.services.borg.storagebox.account` and the agenix secret
          `borg-storagebox-ssh.age` to be populated.
        - `rclone-drive`: borg targets a local sftp endpoint served by
          `rclone serve sftp` pointing at a gdrive-crypt remote. Decision
          deferred; option declared so hosts can opt in once the rclone
          service module exists.
      '';
    };

    storagebox = {
      account = lib.mkOption {
        type = lib.types.str;
        default = "";
        example = "u123456";
        description = "Hetzner Storage Box account name (uXXXXXX). Must be set when target = storagebox.";
      };

      path = lib.mkOption {
        type = lib.types.str;
        default = "backups";
        description = "Subdirectory inside the storage box where the borg repo lives.";
      };

      sshKeyFile = lib.mkOption {
        type = lib.types.path;
        default = "/run/agenix/borg-storagebox-ssh";
        description = "Path to the agenix-decrypted SSH private key for storage-box auth.";
      };

      knownHostsEntry = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = ''
          Optional known_hosts line for the storage-box endpoint. Operator
          fills this in after the first manual SSH handshake.
        '';
      };
    };

    rcloneDrive = {
      host = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = "Host where `rclone serve sftp` is listening.";
      };

      port = lib.mkOption {
        type = lib.types.port;
        default = 2022;
        description = "Port where `rclone serve sftp` is listening.";
      };

      path = lib.mkOption {
        type = lib.types.str;
        default = "borg";
        description = "Path on the rclone-served filesystem to host the borg repo.";
      };
    };

    # Read-only resolution surface for downstream consumers.
    resolved = {
      repo = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        readOnly = true;
        default = resolvedRepo;
        description = ''
          Resolved borg repo URI based on the selected target. `null` for
          `local` (current backup.nix owns local repo paths directly) and
          for `storagebox` when no account is configured yet.
        '';
      };

      target = lib.mkOption {
        type = lib.types.str;
        readOnly = true;
        default = cfg.target;
      };
    };
  };

  config = {
    assertions = [
      {
        assertion = cfg.target != "storagebox" || cfg.storagebox.account != "";
        message = "sinnix.services.borg.target = storagebox requires sinnix.services.borg.storagebox.account to be set.";
      }
    ];
  };
}
