# Storage Infrastructure
#
# Filesystem tools, btrfs maintenance.
# Distinct from features/desktop/storage.nix (user helpers).
{
  pkgs,
  lib,
  config,
  helpers,
  ...
}:
let
  username = config.sinnix.user.name;
  realmRoot = config.sinnix.paths.realmRoot;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  userCfg = lib.attrByPath [ "users" "users" username ] config { };
  primaryGroupName = userCfg.group or "users";
  trashUid = if (userCfg.uid or null) != null then toString userCfg.uid else "1000";
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
    scriptPkgs.sinnix-cache-subvol-convert
  ];
in
{
  environment.systemPackages = lib.mkAfter (baseStoragePackages ++ storageMaintenancePackages);

  systemd.tmpfiles.rules = lib.mkAfter [
    "d ${realmRoot}/.Trash-${trashUid} 0700 ${username} ${primaryGroupName} -"
  ];

  system.activationScripts.fixRclonePermissions.text = ''
    if [ -f ${userHome}/.config/rclone/rclone.conf ]; then
      chown ${username}:${primaryGroupName} ${userHome}/.config/rclone ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
      chmod 600 ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
    fi
  '';
}
