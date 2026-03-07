# Storage Infrastructure
#
# Filesystem tools, btrfs maintenance, Nextcloud WebDAV.
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
  userUid = builtins.toString (userCfg.uid or 1000);
  primaryGroupName = userCfg.group or "users";
  groupCfg = lib.attrByPath [ "users" "groups" primaryGroupName ] config { };
  primaryGroupId = builtins.toString (groupCfg.gid or 100);
  userHome = userCfg.home or "/home/${username}";
  nextcloudUser = config.sinnix.storage.nextcloudUser;
  nextcloudAddressPath = config.sinnix.secrets.paths."nextcloud-address";
  nextcloudCredentialsPath = config.sinnix.secrets.paths."nextcloud-webdav-credentials";
  nextcloudRemoteName = "nextcloud";
  nextcloudMountUnit = "mnt-nextcloud.mount";
  nextcloudAutomountUnit = "mnt-nextcloud.automount";
  nextcloudRcloneConfigDir = "/run/rclone-nextcloud";
  nextcloudRcloneConfigPath = "${nextcloudRcloneConfigDir}/rclone.conf";
  nextcloudRcloneCacheDir = "/var/cache/rclone-nextcloud";
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
  secretsEnabled = config.sinnix.secrets.enable;
in
{
  environment.systemPackages = lib.mkAfter (baseStoragePackages ++ storageMaintenancePackages);

  # Nextcloud WebDAV mount requires the secretized endpoint and credentials.
  programs.fuse.userAllowOther = lib.mkIf secretsEnabled true;

  systemd.tmpfiles.rules = lib.mkAfter [
    "d /mnt/nextcloud 0755 root root -"
    "d ${nextcloudRcloneCacheDir} 0755 root root -"
  ];

  # The appliance exposes Nextcloud on an IP-backed endpoint with a
  # hostname-mismatched cert, so the rclone mount must skip hostname validation
  # until the server-side certificate is fixed.
  system.activationScripts.nextcloudRcloneRuntime = lib.mkIf secretsEnabled {
    deps = [ "agenixInstall" ];
    text = ''
      nextcloud_address_file="${nextcloudAddressPath}"
      nextcloud_credentials_file="${nextcloudCredentialsPath}"
      runtime_config_dir="${nextcloudRcloneConfigDir}"
      runtime_config_path="${nextcloudRcloneConfigPath}"
      runtime_unit_dir=/run/systemd/system
      runtime_wants_dir="$runtime_unit_dir/multi-user.target.wants"
      mount_unit="$runtime_unit_dir/${nextcloudMountUnit}"
      automount_unit="$runtime_unit_dir/${nextcloudAutomountUnit}"
      automount_wanted_by="$runtime_wants_dir/${nextcloudAutomountUnit}"

      cleanup_managed_nextcloud() {
        rm -rf "$runtime_config_dir"
        rm -f "$mount_unit" "$automount_unit" "$automount_wanted_by"
      }

      if [ ! -r "$nextcloud_address_file" ] || [ ! -r "$nextcloud_credentials_file" ]; then
        echo "WARNING: Nextcloud secrets missing; disabling Nextcloud mount units" >&2
        ${pkgs.systemd}/bin/systemctl stop ${nextcloudAutomountUnit} ${nextcloudMountUnit} >/dev/null 2>&1 || true
        cleanup_managed_nextcloud
        ${pkgs.systemd}/bin/systemctl daemon-reload >/dev/null 2>&1 || true
      else
        nextcloud_address="$(${pkgs.coreutils}/bin/tr -d '\r\n' < "$nextcloud_address_file")"
        cleanup_managed_nextcloud
        ${pkgs.coreutils}/bin/mkdir -p "$runtime_wants_dir"
        ${pkgs.coreutils}/bin/mkdir -p "$runtime_config_dir"
        chmod 700 "$runtime_config_dir"

        read -r _nextcloud_url _nextcloud_credentials_user nextcloud_password < "$nextcloud_credentials_file"
        if [ -z "$nextcloud_address" ] || [ -z "$nextcloud_password" ]; then
          echo "WARNING: malformed Nextcloud credentials secret; disabling Nextcloud mount units" >&2
          ${pkgs.systemd}/bin/systemctl stop ${nextcloudAutomountUnit} ${nextcloudMountUnit} >/dev/null 2>&1 || true
          cleanup_managed_nextcloud
          ${pkgs.systemd}/bin/systemctl daemon-reload >/dev/null 2>&1 || true
          exit 0
        fi
        obscured_password="$(${pkgs.rclone}/bin/rclone obscure "$nextcloud_password")"

        cat > "$runtime_config_path" <<EOF
[${nextcloudRemoteName}]
type = webdav
url = https://$nextcloud_address/nextcloud/remote.php/dav/files/${nextcloudUser}/
vendor = nextcloud
user = ${nextcloudUser}
pass = $obscured_password
EOF
        chmod 600 "$runtime_config_path"

        cat > "$mount_unit" <<EOF
[Unit]
Description=Nextcloud WebDAV mount via rclone
After=network-online.target
Wants=network-online.target
ConditionPathExists=${nextcloudRcloneConfigPath}

[Mount]
What=${nextcloudRemoteName}:
Where=/mnt/nextcloud
Type=rclone
Options=rw,_netdev,noauto,nosuid,nodev,args2env,allow_other,config=${nextcloudRcloneConfigPath},cache_dir=${nextcloudRcloneCacheDir},vfs_cache_mode=writes,dir_cache_time=10m,uid=${userUid},gid=${primaryGroupId},file_perms=0644,dir_perms=0755,no_check_certificate
EOF

        cat > "$automount_unit" <<EOF
[Unit]
Description=Nextcloud WebDAV automount via rclone
After=network-online.target
Wants=network-online.target

[Automount]
Where=/mnt/nextcloud
TimeoutIdleSec=600

[Install]
WantedBy=multi-user.target
EOF

        ${pkgs.coreutils}/bin/ln -s ../${nextcloudAutomountUnit} "$automount_wanted_by"
        ${pkgs.systemd}/bin/systemctl daemon-reload
        ${pkgs.systemd}/bin/systemctl restart ${nextcloudAutomountUnit} >/dev/null 2>&1 \
          || ${pkgs.systemd}/bin/systemctl start ${nextcloudAutomountUnit}
      fi
    '';
  };

  system.activationScripts.fixRclonePermissions.text = ''
    if [ -f ${userHome}/.config/rclone/rclone.conf ]; then
      chown ${username}:${primaryGroupName} ${userHome}/.config/rclone ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
      chmod 600 ${userHome}/.config/rclone/rclone.conf 2>/dev/null || true
    fi
  '';
}
