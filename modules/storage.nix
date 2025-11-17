{
  pkgs,
  lib,
  inputs,
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
  nextcloudCert = builtins.readFile "${inputs.self}/assets/nextcloud-cert.crt";
  baseStoragePackages = with pkgs; [
    davfs2
    rclone
    onedrive
    fuse
    fuse3
    rsync
  ];
  storageMaintenancePackages = with pkgs; [
    btrfs-progs
    hdparm
    smartmontools
    nvme-cli
    parted
    fio
    ioping
    udisks2
    extundelete
    lvm2
    xfsprogs
    e2fsprogs
  ];
in
{
  environment = {
    systemPackages = lib.mkAfter (baseStoragePackages ++ storageMaintenancePackages);

    etc = {
      "davfs2/secrets" = {
        source = config.sinnix.secrets.paths.davfs2-secrets;
        mode = "0600";
        user = "root";
        group = "root";
      };

      "davfs2/certs/nextcloud-host.pem" = {
        mode = "0644";
        text = nextcloudCert;
      };

      "davfs2/servers/nextcloud-host".text = ''
        servercert sha256:0E:BA:10:DB:78:60:43:37:BD:5C:0A:60:BA:71:04:4A:FD:BF:84:D4:62:40:4A:63:8D:CD:12:5F:D4:BE:7E:8D
      '';

      "onedrive/config".text = ''
        sync_dir = "/var/lib/onedrive"
        skip_file = "~*|.~*|*.tmp|*.partial"
        skip_dir = "backup|archive|Obrazy|Samsung Health|samsunghealth_ezo.dev_20240704190449|Załączniki e-mail"
        monitor_interval = "300"
        rate_limit = "0"
      '';

      "onedrive/sync_list".text = ''
        Documents
      '';
    };
  };

  security.pki.certificates = lib.mkAfter [ nextcloudCert ];

  services.davfs2 = {
    enable = true;
    settings.globalSection = {
      use_locks = "0";
      cache_size = "5120";
      cache_dir = "/var/cache/davfs2";
      delay_upload = "10";
    };
  };

  systemd.tmpfiles.rules = lib.mkAfter [
    "d /mnt/nextcloud 0755 root root -"
    "d /mnt/gdrive 0755 ${username} ${primaryGroupName} -"
    "d /var/lib/onedrive 0755 ${username} ${primaryGroupName} -"
    "L /mnt/onedrive - - - - /var/lib/onedrive"
    "d /var/lib/onedrive-auth 0700 ${username} ${primaryGroupName} -"
  ];

  systemd.services =
    let
      ensureOnedriveState = pkgs.writeShellScript "onedrive-sync-setup" ''
        set -euo pipefail

        data_dir=/var/lib/onedrive
        auth_dir=/var/lib/onedrive-auth

        install -d -m755 -o ${username} -g ${primaryGroupName} "$data_dir"
        install -d -m700 -o ${username} -g ${primaryGroupName} "$auth_dir"

        if [ ! -f "$auth_dir/config" ]; then
          if [ -d /etc/onedrive ]; then
            cp -r /etc/onedrive/. "$auth_dir"/
          fi
          chown -R ${username}:${primaryGroupName} "$auth_dir"
        fi
      '';

      launchOnedrive = pkgs.writeShellScript "onedrive-sync-service" ''
        set -euo pipefail

        auth_dir=/var/lib/onedrive-auth

        warned=0
        while [ ! -f "$auth_dir/refresh_token" ]; do
          if [ "$warned" -eq 0 ]; then
            echo "onedrive-sync: waiting for $auth_dir/refresh_token (run 'onedrive-auth' to authorise)" >&2
            warned=1
          fi
          sleep 30
        done

        exec ${pkgs.onedrive}/bin/onedrive --monitor --confdir "$auth_dir"
      '';
    in
    {
      onedrive-sync = {
        description = "OneDrive Selective Synchronization";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        wantedBy = [ "multi-user.target" ];
        enable = true;
        serviceConfig = {
          Type = "simple";
          User = username;
          Group = primaryGroupName;
          PermissionsStartOnly = true;
          ExecStartPre = [ ensureOnedriveState ];
          ExecStart = launchOnedrive;
          Restart = "on-failure";
          RestartSec = 3;
          ReadWritePaths = [
            "/var/lib/onedrive"
            "/var/lib/onedrive-auth"
          ];
        };
      };

      gdrive-mount = {
        enable = false;
      };
    };

  system.activationScripts.fixRclonePermissions.text = ''
    if [ -f /home/${username}/.config/rclone/rclone.conf ]; then
      chown ${username}:${primaryGroupName} /home/${username}/.config/rclone /home/${username}/.config/rclone/rclone.conf 2>/dev/null || true
      chmod 600 /home/${username}/.config/rclone/rclone.conf 2>/dev/null || true
    fi
  '';

  fileSystems."/mnt/nextcloud" = {
    device = "https://nextcloud-host/remote.php/dav/files/USER/";
    fsType = "davfs";
    noCheck = true;
    options = [
      "noauto"
      "x-systemd.automount"
      "x-systemd.idle-timeout=600"
      "_netdev"
      "uid=${userUid}"
      "gid=${primaryGroupId}"
      "dir_mode=0755"
      "file_mode=0644"
    ];
  };
}
