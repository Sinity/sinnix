# Storage Automation - Nextcloud and Encryption
{ pkgs, lib, ... }:

let
  nextcloudCert = builtins.readFile ../asset/nextcloud-cert.crt;
in
{
  # Cloud storage and encryption support
  environment = {
    systemPackages = with pkgs; [
      # WebDAV/Nextcloud
      davfs2

      # Multi-cloud support
      rclone

      # OneDrive
      onedrive

      # Google Drive (using rclone)

      # Encryption
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

      "davfs2/servers/nextcloud-host" = {
        text = ''
          servercert sha256:0E:BA:10:DB:78:60:43:37:BD:5C:0A:60:BA:71:04:4A:FD:BF:84:D4:62:40:4A:63:8D:CD:12:5F:D4:BE:7E:8D
        '';
      };

      "onedrive/config" = {
        text = ''
          # OneDrive configuration with selective sync
          sync_dir = "/var/lib/onedrive"
          skip_file = "~*|.~*|*.tmp|*.partial"
          # Skip all folders except Documents
          skip_dir = "backup|archive|Obrazy|Samsung Health|samsunghealth_ezo.dev_20240704190449|Załączniki e-mail"
          monitor_interval = "300"
          # Upload/download rate limit (KB/s) - 0 = unlimited
          rate_limit = "0"
        '';
      };

      "onedrive/sync_list" = {
        text = ''
          # Selective sync - only sync these folders (keep under 5GB)
          Documents
          # Uncomment to add more folders:
          # Important
          # Projects
        '';
      };
    };
  };

  security.pki.certificates = lib.mkAfter [ nextcloudCert ];

  # Enable davfs2 for WebDAV mounting with caching
  services.davfs2 = {
    enable = true;
    settings = {
      globalSection = {
        use_locks = "0";
        cache_size = "5120"; # 5GB cache limit
        cache_dir = "/var/cache/davfs2";
        delay_upload = "10";
      };
    };
  };

  # Create mount points, supporting services, and helper configuration
  systemd = {
    tmpfiles.rules = [
      "d /mnt/nextcloud 0755 root root -"
      "d /mnt/gdrive 0755 sinity users -"
      "d /var/lib/onedrive 0755 sinity users -"
      "L /mnt/onedrive - - - - /var/lib/onedrive"
      # OneDrive auth files need to be writable
      "d /var/lib/onedrive-auth 0700 sinity users -"
      "d /outer-realm/inbox 2775 sinity users -"
    ];

    services = {
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
  };

  # Automount Nextcloud on demand via davfs2
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

  # User configuration
  home-manager.users.sinity = {
    home = {
      packages = with pkgs; [
        # Encryption tools
        gocryptfs
        encfs
        cryptsetup

        # Convenience scripts
        (writeShellScriptBin "encrypt-folder" ''
          #!/usr/bin/env bash
          set -euo pipefail

          if [ $# -ne 2 ]; then
            echo "Usage: encrypt-folder <source-folder> <encrypted-folder>"
            echo "Example: encrypt-folder ~/Documents ~/Documents.encrypted"
            exit 1
          fi

          SOURCE="$1"
          ENCRYPTED="$2"

          if [ ! -d "$SOURCE" ]; then
            echo "Error: Source folder does not exist"
            exit 1
          fi

          mkdir -p "$ENCRYPTED"

          echo "Initializing encrypted folder..."
          gocryptfs -init "$ENCRYPTED"

          # Create mount point
          MOUNT_POINT="/tmp/encrypt-mount-$$"
          mkdir -p "$MOUNT_POINT"

          echo "Mounting encrypted folder..."
          gocryptfs "$ENCRYPTED" "$MOUNT_POINT"

          echo "Copying files..."
          rsync -av --progress "$SOURCE/" "$MOUNT_POINT/"

          echo "Unmounting..."
          fusermount -u "$MOUNT_POINT"
          rmdir "$MOUNT_POINT"

          echo "Done! Encrypted folder created at: $ENCRYPTED"
          echo "To mount: gocryptfs $ENCRYPTED <mount-point>"
        '')

        (writeShellScriptBin "decrypt-folder" ''
          #!/usr/bin/env bash
          set -euo pipefail

          if [ $# -ne 2 ]; then
            echo "Usage: decrypt-folder <encrypted-folder> <mount-point>"
            echo "Example: decrypt-folder ~/Documents.encrypted ~/Documents"
            exit 1
          fi

          ENCRYPTED="$1"
          MOUNT_POINT="$2"

          if [ ! -d "$ENCRYPTED" ]; then
            echo "Error: Encrypted folder does not exist"
            exit 1
          fi

          mkdir -p "$MOUNT_POINT"

          echo "Mounting encrypted folder..."
          gocryptfs "$ENCRYPTED" "$MOUNT_POINT"

          echo "Mounted at: $MOUNT_POINT"
          echo "To unmount: fusermount -u $MOUNT_POINT"
        '')

        (writeShellScriptBin "mount-nextcloud" ''
          #!/usr/bin/env bash
          set -euo pipefail

          # Check if already mounted
          if mountpoint -q /mnt/nextcloud; then
            echo "Nextcloud is already mounted"
            exit 0
          fi

          echo "Mounting Nextcloud..."
          sudo mount /mnt/nextcloud

          echo "Nextcloud mounted at /mnt/nextcloud"
        '')

        (writeShellScriptBin "umount-nextcloud" ''
          #!/usr/bin/env bash
          set -euo pipefail

          if ! mountpoint -q /mnt/nextcloud; then
            echo "Nextcloud is not mounted"
            exit 0
          fi

          echo "Unmounting Nextcloud..."
          sudo umount /mnt/nextcloud
          echo "Nextcloud unmounted"
        '')

        # OneDrive scripts

        (writeShellScriptBin "onedrive-auth" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "=== OneDrive Authentication ==="
          echo
          echo "OneDrive is configured to sync to /var/lib/onedrive (accessible via /mnt/onedrive symlink)"
          echo "Selective sync enabled: Only 'Documents' folder will sync"
          echo

          # Ensure auth directory exists with proper permissions
          sudo mkdir -p /var/lib/onedrive-auth
          sudo chown sinity:users /var/lib/onedrive-auth
          sudo chmod 700 /var/lib/onedrive-auth

          # Copy config if not exists
          if [ ! -f /var/lib/onedrive-auth/config ]; then
            sudo cp -r /etc/onedrive/* /var/lib/onedrive-auth/
            sudo chown -R sinity:users /var/lib/onedrive-auth/
          fi

          echo "To authenticate OneDrive:"
          echo "1. Run: onedrive --confdir /var/lib/onedrive-auth"
          echo "2. Visit the URL shown and sign in with your Microsoft account"
          echo "3. Copy the response URL and paste it when prompted"
          echo
          echo "After authentication, restart the service with: sudo systemctl restart onedrive-sync"
          echo
          systemctl status onedrive-sync --no-pager
        '')

        (writeShellScriptBin "onedrive-status" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "OneDrive Status:"
          echo "================"

          sync_dirs=""
          if [ -f /etc/onedrive/sync_list ]; then
            sync_dirs=$(grep -v '^#' /etc/onedrive/sync_list 2>/dev/null | xargs || true)
          fi

          if [ -L /mnt/onedrive ] && [ -d "$(readlink /mnt/onedrive)" ]; then
            echo "✓ Sync location: /var/lib/onedrive (via /mnt/onedrive symlink)"
            if [ -n "$sync_dirs" ]; then
              echo "✓ Selective sync: $sync_dirs"
            else
              echo "✓ Selective sync: (none configured)"
            fi
            echo "✓ Current size: $(du -sh /var/lib/onedrive 2>/dev/null | cut -f1)"
            echo
            systemctl status onedrive-sync --no-pager
          else
            echo "✗ OneDrive not properly configured"
            echo "Run: onedrive-auth to set up authentication"
          fi
        '')

        (writeShellScriptBin "umount-onedrive" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "Stopping OneDrive synchronization service..."
          if sudo systemctl stop onedrive-sync; then
            echo "OneDrive sync service stopped"
          else
            echo "Failed to stop onedrive-sync" >&2
            exit 1
          fi
        '')

        # Google Drive scripts
        (writeShellScriptBin "setup-gdrive" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "Setting up Google Drive with rclone..."
          echo "Follow the prompts to authenticate"

          rclone config create gdrive drive scope drive

          echo "Google Drive setup complete!"
          echo "To mount: mount-gdrive"
        '')

        (writeShellScriptBin "mount-gdrive" ''
          #!/usr/bin/env bash
          set -euo pipefail

          command -v rclone >/dev/null 2>&1 || { echo "rclone not found" >&2; exit 1; }
          command -v fusermount3 >/dev/null 2>&1 || { echo "fusermount3 not found" >&2; exit 1; }

          if [ ! -f "$HOME/.config/rclone/rclone.conf" ]; then
            echo "rclone config not found at $HOME/.config/rclone/rclone.conf" >&2
            exit 1
          fi

          if mountpoint -q /mnt/gdrive; then
            echo "Google Drive is already mounted"
            exit 0
          fi

          # Kill any existing rclone processes for gdrive
          pkill -f "rclone.*gdrive" || true
          sleep 1

          echo "Mounting Google Drive..."
          rclone mount gdrive: /mnt/gdrive \
            --daemon \
            --vfs-cache-mode full \
            --vfs-cache-max-size 5G \
            --vfs-cache-max-age 72h \
            --buffer-size 256M \
            --vfs-read-ahead 512M \
            --dir-cache-time 72h \
            --poll-interval 1m \
            --uid $(id -u) \
            --gid $(id -g) \
            --umask 022 \
            --config "$HOME/.config/rclone/rclone.conf"

          sleep 2
          if mountpoint -q /mnt/gdrive; then
            echo "Google Drive mounted at /mnt/gdrive"
          else
            echo "Failed to mount Google Drive"
            exit 1
          fi
        '')

        (writeShellScriptBin "umount-gdrive" ''
          #!/usr/bin/env bash
          set -euo pipefail

          command -v fusermount3 >/dev/null 2>&1 || { echo "fusermount3 not found" >&2; exit 1; }

          if ! mountpoint -q /mnt/gdrive; then
            echo "Google Drive is not mounted"
            exit 0
          fi

          echo "Unmounting Google Drive..."
          fusermount3 -u /mnt/gdrive
          echo "Google Drive unmounted"
        '')

        # Universal cloud storage manager
        (writeShellScriptBin "cloud-status" ''
          #!/usr/bin/env bash
          set -euo pipefail

          echo "Cloud Storage Status:"
          echo "===================="

          echo -n "Nextcloud: "
          mountpoint -q /mnt/nextcloud && echo "✓ Mounted" || echo "✗ Not mounted"

          echo -n "OneDrive:  "
          if systemctl is-active --quiet onedrive-sync; then
            echo "✓ Service active"
          else
            echo "✗ Service inactive"
          fi

          echo -n "G Drive:   "
          mountpoint -q /mnt/gdrive && echo "✓ Mounted" || echo "✗ Not mounted"

          echo ""
          echo "Encryption Status:"
          echo "=================="
          if mount | grep -q gocryptfs; then
            mount | awk '/gocryptfs/ {print "✓", $3}'
          else
            echo "No encrypted folders mounted"
          fi
        '')
      ];

      shellAliases = {
        # Nextcloud
        nc-mount = "mount-nextcloud";
        nc-umount = "umount-nextcloud";

        # OneDrive
        od-auth = "onedrive-auth";
        od-status = "onedrive-status";

        # Google Drive
        gd-setup = "setup-gdrive";
        gd-mount = "mount-gdrive";
        gd-umount = "umount-gdrive";

        # Cloud status
        cloud = "cloud-status";

        # Encryption
        enc = "encrypt-folder";
        dec = "decrypt-folder";

        # Quick encrypt/decrypt for common folders
        enc-docs = "encrypt-folder ~/Documents ~/Documents.encrypted";
        dec-docs = "decrypt-folder ~/Documents.encrypted ~/Documents.decrypted";
      };
    };
  };

  # Add user to davfs2 group without clobbering other group membership
  users.users.sinity.extraGroups = lib.mkAfter [ "davfs2" ];

  # Exclude cloud mounts from file indexers to prevent slowdowns
  environment.etc."xdg/autostart/tracker-miner-fs-3.desktop".text = ''
    [Desktop Entry]
    Hidden=true
  '';

  # Configure updatedb to skip cloud mounts
  services.locate = {
    enable = true;
    pruneBindMounts = true;
    prunePaths = [
      "/mnt/nextcloud"
      "/mnt/onedrive"
      "/mnt/gdrive"
    ];
  };
}
