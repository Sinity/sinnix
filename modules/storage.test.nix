{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  ...
}:
{
  name = "nextcloud-storage-wiring";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "nextcloud-storage-test";
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
        assertion = config.age.secrets ? "nextcloud-address";
        message = "Agenix must define the nextcloud-address secret";
      }
      {
        assertion = config.age.secrets ? "borg-passphrase";
        message = "Agenix must define the borg-passphrase secret";
      }
      {
        assertion = config.age.secrets ? "nextcloud-webdav-credentials";
        message = "Agenix must still define the Nextcloud credentials secret";
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
        assertion = !(config.system.activationScripts ? nextcloudRcloneRuntime);
        message = "Legacy Nextcloud runtime mount-unit rendering must remain disabled until the boot-cycle issue is fixed";
      }
    ];
}
