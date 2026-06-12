{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  inputs,
  ...
}:
{
  name = "storage-rclone-backup-wiring";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "storage-wiring-test";
      }
    )
  ];
  assertions =
    config:
    let
      fixRclonePermissions = config.system.activationScripts.fixRclonePermissions.text or "";
      packageNames = map (pkg: lib.getName pkg) config.environment.systemPackages;
      cacheConvertScript = builtins.readFile (inputs.self + "/scripts/sinnix-cache-subvol-convert");
    in
    [
      {
        assertion = config.system.activationScripts ? fixRclonePermissions;
        message = "Rclone credential permissions must be repaired at activation time";
      }
      {
        assertion = lib.hasInfix ".config/rclone/rclone.conf" fixRclonePermissions;
        message = "Rclone permission repair must target the user's persisted rclone config";
      }
      {
        assertion = lib.hasInfix "chmod 600" fixRclonePermissions;
        message = "Rclone permission repair must lock the credentials file to mode 600";
      }
      {
        assertion = builtins.elem "d /realm/.Trash-1000 0700 sinity users -" config.systemd.tmpfiles.rules;
        message = "Realm mount must expose a FreeDesktop trash directory for file managers";
      }
      {
        assertion = builtins.elem "sinnix-cache-subvol-convert" packageNames;
        message = "Storage maintenance tools must install the guarded cache subvolume converter";
      }
      {
        assertion =
          lib.hasInfix "Default path: /persist/home/sinity/.cache" cacheConvertScript
          && lib.hasInfix "run as root" cacheConvertScript
          && lib.hasInfix "Re-run with --yes --discard-existing" cacheConvertScript
          && lib.hasInfix "Existing cache contents are present" cacheConvertScript
          && lib.hasInfix "active mount source" cacheConvertScript
          && lib.hasInfix "Stop the user session or unmount the bind target before conversion." cacheConvertScript
          && lib.hasInfix "btrfs subvolume create" cacheConvertScript
          && lib.hasInfix "chattr +C" cacheConvertScript
          && lib.hasInfix "rm -rf --one-file-system" cacheConvertScript;
        message = "Cache subvolume conversion must stay explicit, nodatacow, and guarded against accidental cache deletion";
      }
    ];
}
