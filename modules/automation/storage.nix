{ pkgs, lib, inputs, ... }:
let
  nextcloudCert = builtins.readFile "${inputs.self}/assets/nextcloud-cert.crt";
in
{
  environment = {
    systemPackages = with pkgs; [
      davfs2
      rclone
      onedrive
      gocryptfs
      encfs
      cryptsetup
      fuse
      fuse3
      rsync
    ];

    etc = {
      "davfs2/secrets" = {
        source = "/run/agenix/davfs2-secrets";
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
    "d /mnt/gdrive 0755 sinity users -"
    "d /var/lib/onedrive 0755 sinity users -"
    "L /mnt/onedrive - - - - /var/lib/onedrive"
    "d /var/lib/onedrive-auth 0700 sinity users -"
    "d /outer-realm/inbox 2775 sinity users -"
  ];

  systemd.services = {
    onedrive-sync = {
      description = "OneDrive Selective Synchronization";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ ];
      enable = false;
      preStart = ''
        if [ ! -f /var/lib/onedrive-auth/config ]; then
          cp -r /etc/onedrive/* /var/lib/onedrive-auth/ || true
        fi
      '';
      serviceConfig = {
        Type = "simple";
        User = "sinity";
        Group = "users";
        ExecStart = "${pkgs.onedrive}/bin/onedrive --monitor --confdir /var/lib/onedrive-auth";
        Restart = "on-failure";
        RestartSec = 3;
        ReadWritePaths = [
          "/var/lib/onedrive"
          "/var/lib/onedrive-auth"
        ];
      };
    };

    gdrive-mount = {
      description = "Mount Google Drive via rclone";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ ];
      enable = false;
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = "sinity";
        ConditionPathExists = "/home/sinity/.config/rclone/rclone.conf";
        ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p /mnt/gdrive";
        ExecStart = "${pkgs.rclone}/bin/rclone mount gdrive: /mnt/gdrive --config /home/sinity/.config/rclone/rclone.conf --daemon --vfs-cache-mode full --vfs-cache-max-size 5G --vfs-cache-max-age 72h --buffer-size 256M --vfs-read-ahead 512M --dir-cache-time 72h --poll-interval 1m --uid 1000 --gid 100 --umask 022";
        ExecStop = "${pkgs.fuse3}/bin/fusermount3 -u /mnt/gdrive";
      };
    };
  };

  fileSystems."/mnt/nextcloud" = {
    device = "https://nextcloud-host/remote.php/dav/files/USER/";
    fsType = "davfs";
    options = [
      "noauto"
      "x-systemd.automount"
      "x-systemd.idle-timeout=600"
      "_netdev"
      "uid=1000"
      "gid=100"
      "dir_mode=0755"
      "file_mode=0644"
    ];
  };
}
