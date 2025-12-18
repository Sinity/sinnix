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
	  getAttrOrFallback =
	    set: attr: fallback:
	    let
	      value = set.${attr} or null;
	    in
	    if value == null then fallback else value;
  userUid = builtins.toString (getAttrOrFallback userCfg "uid" 1000);
  primaryGroupName = getAttrOrFallback userCfg "group" "users";
  groupCfg = lib.attrByPath [ "users" "groups" primaryGroupName ] config { };
  primaryGroupId = builtins.toString (getAttrOrFallback groupCfg "gid" 100);
  nextcloudCert = builtins.readFile "${inputs.self}/assets/nextcloud-cert.crt";
  baseStoragePackages = with pkgs; [
    davfs2
    rclone
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
  ];

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
