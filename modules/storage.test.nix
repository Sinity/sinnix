{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
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
      packageNames = map (pkg: lib.getName pkg) config.environment.systemPackages;
    in
    [
      {
        assertion = config.system.activationScripts ? fixRclonePermissions;
        message = "Rclone credential permissions must be repaired at activation time";
      }
      {
        assertion = builtins.elem "d /realm/.Trash-1000 0700 sinity users -" config.systemd.tmpfiles.rules;
        message = "Realm mount must expose a FreeDesktop trash directory for file managers";
      }
      {
        assertion = builtins.elem "sinnix-cache-subvol-convert" packageNames;
        message = "Storage maintenance tools must install the guarded cache subvolume converter";
      }
    ];
}
