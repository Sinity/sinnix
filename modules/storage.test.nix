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
    [
      {
        assertion = config.system.activationScripts ? fixRclonePermissions;
        message = "Rclone credential permissions must be repaired at activation time";
      }
      {
        assertion = builtins.elem "d /realm/.Trash-1000 0700 sinity users -" config.systemd.tmpfiles.rules;
        message = "Realm mount must expose a FreeDesktop trash directory for file managers";
      }
    ];
}
