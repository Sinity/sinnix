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
      fixRclonePermissions = config.system.activationScripts.fixRclonePermissions.text or "";
    in
    [
      {
        assertion = config.age.secrets ? "borg-passphrase";
        message = "Agenix must define the borg-passphrase secret";
      }
      {
        assertion = config.services.borgbackup.jobs.realm.encryption.mode == "repokey-blake2";
        message = "Realm Borg job must use repokey-blake2";
      }
      {
        assertion = config.services.borgbackup.jobs.persist.encryption.mode == "repokey-blake2";
        message = "Persist Borg job must use repokey-blake2";
      }
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
    ];
}
