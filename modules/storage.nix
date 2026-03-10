# Storage Infrastructure
#
# Filesystem tools, btrfs maintenance.
# Distinct from features/desktop/storage.nix (user helpers).
{
  pkgs,
  lib,
  config,
  ...
}:
let
  username = config.sinnix.user.name;
  userCfg = lib.attrByPath [ "users" "users" username ] config { };
  primaryGroupName = userCfg.group or "users";
  userHome = userCfg.home or "/home/${username}";
  baseStoragePackages = with pkgs; [
    rclone
    fuse
    fuse3
    rsync
  ];
  storageMaintenancePackages = with pkgs; [
    btrfs-progs
    parted
    ioping
    udisks2
    extundelete
    lvm2
    xfsprogs
    e2fsprogs
  ];
in
{
  environment.systemPackages = lib.mkAfter (baseStoragePackages ++ storageMaintenancePackages);

  # Nextcloud WebDAV mount — DISABLED 2026-03-10 during recovery.
  # Caused a systemd ordering cycle (mnt-nextcloud.automount vs local-fs.target)
  # that contributed to boot failures. Re-enable after fixing the automount unit
  # to not depend on network-online.target (automounts don't need it).

  system.activationScripts.fixRclonePermissions.text = ''
    if [ -f ${userHome}/.config/rclone/rclone.conf ]; then
      chown ${username}:${primaryGroupName} ${userHome}/.config/rclone ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
      chmod 600 ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
    fi
  '';
}
