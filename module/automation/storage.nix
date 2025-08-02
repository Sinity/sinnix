# Storage Automation - Nextcloud and Encryption
{ pkgs, ... }:

{
  # Cloud storage and encryption support
  environment.systemPackages = with pkgs; [
    # WebDAV/Nextcloud
    davfs2
    
    # Multi-cloud support
    rclone
    
    # OneDrive
    onedrive
    
    # Google Drive (via rclone or ocamlfuse)
    google-drive-ocamlfuse
    
    # Encryption
    gocryptfs
    encfs
    cryptsetup
  ];

  # Enable davfs2 for WebDAV mounting with caching
  services.davfs2 = {
    enable = true;
    settings = {
      globalSection = {
        use_locks = "0";
        cache_size = "5120";        # 5GB cache limit
        cache_dir = "/var/cache/davfs2";
        delay_upload = "10";
      };
    };
  };

  # Configure davfs2 secrets for system-wide mounting
  environment.etc."davfs2/secrets" = {
    text = ''
      # Nextcloud WebDAV credentials
      http://nextcloud-host/remote.php/dav/files/USER/ USER REDACTED_CREDENTIALS
    '';
    mode = "0600";
    user = "root";
    group = "root";
  };

  # Create mount points and cache directories
  systemd.tmpfiles.rules = [
    "d /mnt/nextcloud 0755 root root -"
    "d /mnt/onedrive 0755 root root -"
    "d /mnt/gdrive 0755 root root -"
    "d /var/lib/onedrive 0755 sinity users -"
    "L+ /mnt/onedrive - - - - /var/lib/onedrive"
    # OneDrive auth files need to be writable
    "d /var/lib/onedrive-auth 0700 sinity users -"
  ];

  # Nextcloud mount service (automatic mounting)
  systemd.services.nextcloud-mount = {
    description = "Mount Nextcloud via WebDAV";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStartPre = "${pkgs.coreutils}/bin/test -d /mnt/nextcloud";
      ExecStart = "${pkgs.davfs2}/bin/mount.davfs http://nextcloud-host/remote.php/dav/files/USER/ /mnt/nextcloud -o uid=1000,gid=100,dir_mode=0755,file_mode=0644";
      ExecStop = "${pkgs.umount}/bin/umount /mnt/nextcloud";
    };
  };

  # OneDrive selective sync service (limited to ~5GB)
  systemd.services.onedrive-sync = {
    description = "OneDrive Selective Synchronization";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    
    # Copy config files to writable location on first run
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
      # Ensure the service can write to both locations
      ReadWritePaths = [ "/var/lib/onedrive" "/var/lib/onedrive-auth" ];
    };
  };

  # OneDrive configuration for selective sync
  environment.etc."onedrive/config" = {
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
  
  environment.etc."onedrive/sync_list" = {
    text = ''
      # Selective sync - only sync these folders (keep under 5GB)
      Documents
      # Uncomment to add more folders:
      # Important
      # Projects
    '';
  };

  # Google Drive mount service (automatic mounting)
  systemd.services.gdrive-mount = {
    description = "Mount Google Drive via rclone";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "sinity";
      ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p /mnt/gdrive";
      ExecStart = "${pkgs.rclone}/bin/rclone mount gdrive: /mnt/gdrive --daemon --vfs-cache-mode full --vfs-cache-max-size 5G --vfs-cache-max-age 72h --buffer-size 256M --vfs-read-ahead 512M --dir-cache-time 72h --poll-interval 1m --allow-other --uid 1000 --gid 100 --umask 022";
      ExecStop = "${pkgs.fuse}/bin/fusermount -u /mnt/gdrive";
    };
  };

  # User configuration
  home-manager.users.sinity = {
    home.packages = with pkgs; [
      # Encryption tools
      gocryptfs
      encfs
      cryptsetup
      
      # Convenience scripts
      (writeShellScriptBin "encrypt-folder" ''
        #!/usr/bin/env bash
        set -e
        
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
        set -e
        
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
        set -e
        
        # Check if already mounted
        if mountpoint -q /mnt/nextcloud; then
          echo "Nextcloud is already mounted"
          exit 0
        fi
        
        echo "Mounting Nextcloud..."
        echo "You'll be prompted for your Nextcloud password"
        
        sudo mount -t davfs http://nextcloud-host/remote.php/dav/files/USER/ /mnt/nextcloud \
          -o uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644,conf=/etc/davfs2/davfs2.conf
        
        echo "Nextcloud mounted at /mnt/nextcloud"
      '')
      
      (writeShellScriptBin "umount-nextcloud" ''
        #!/usr/bin/env bash
        
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
        
        echo "OneDrive Status:"
        echo "================"
        
        if [ -L /mnt/onedrive ] && [ -d "$(readlink /mnt/onedrive)" ]; then
          echo "✓ Sync location: /var/lib/onedrive (via /mnt/onedrive symlink)"
          echo "✓ Selective sync: $(cat /etc/onedrive/sync_list 2>/dev/null | grep -v '^#' | xargs)"
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
        
        if ! mountpoint -q /mnt/onedrive; then
          echo "OneDrive is not mounted"
          exit 0
        fi
        
        echo "Unmounting OneDrive..."
        sudo fusermount -u /mnt/onedrive
        echo "OneDrive unmounted"
      '')
      
      # Google Drive scripts
      (writeShellScriptBin "setup-gdrive" ''
        #!/usr/bin/env bash
        set -e
        
        echo "Setting up Google Drive with rclone..."
        echo "Follow the prompts to authenticate"
        
        rclone config create gdrive drive scope drive
        
        echo "Google Drive setup complete!"
        echo "To mount: mount-gdrive"
      '')
      
      (writeShellScriptBin "mount-gdrive" ''
        #!/usr/bin/env bash
        set -e
        
        if mountpoint -q /mnt/gdrive; then
          echo "Google Drive is already mounted"
          exit 0
        fi
        
        # Kill any existing rclone processes for gdrive
        pkill -f "rclone.*gdrive" || true
        sleep 1
        
        echo "Mounting Google Drive..."
        sudo rclone mount gdrive: /mnt/gdrive \
          --daemon \
          --vfs-cache-mode full \
          --vfs-cache-max-size 5G \
          --vfs-cache-max-age 72h \
          --buffer-size 256M \
          --vfs-read-ahead 512M \
          --dir-cache-time 72h \
          --poll-interval 1m \
          --allow-other \
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
        
        if ! mountpoint -q /mnt/gdrive; then
          echo "Google Drive is not mounted"
          exit 0
        fi
        
        echo "Unmounting Google Drive..."
        fusermount -u /mnt/gdrive
        echo "Google Drive unmounted"
      '')
      
      # Universal cloud storage manager
      (writeShellScriptBin "cloud-status" ''
        #!/usr/bin/env bash
        
        echo "Cloud Storage Status:"
        echo "===================="
        
        echo -n "Nextcloud: "
        mountpoint -q /mnt/nextcloud && echo "✓ Mounted" || echo "✗ Not mounted"
        
        echo -n "OneDrive:  "
        mountpoint -q /mnt/onedrive && echo "✓ Mounted" || echo "✗ Not mounted"
        
        echo -n "G Drive:   "
        mountpoint -q /mnt/gdrive && echo "✓ Mounted" || echo "✗ Not mounted"
        
        echo ""
        echo "Encryption Status:"
        echo "=================="
        mount | grep gocryptfs | awk '{print "✓", $3}' || echo "No encrypted folders mounted"
      '')
    ];

    # Convenience aliases
    home.shellAliases = {
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

    # Create davfs2 directory and secrets
    home.file.".davfs2/secrets" = {
      text = ''
        # Nextcloud WebDAV credentials
        http://nextcloud-host/remote.php/dav/files/USER/ USER REDACTED_CREDENTIALS
      '';
      onChange = ''
        chmod 600 "$HOME/.davfs2/secrets"
      '';
    };
  };

  # Add user to davfs2 group
  users.users.sinity.extraGroups = [ "davfs2" ];

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