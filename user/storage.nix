{
  pkgs,
  sinnix,
  ...
}:
let
  username = sinnix.user.name;
  encryptFolder = pkgs.writeShellScriptBin "encrypt-folder" ''
    #!/usr/bin/env bash
    set -euo pipefail

    if [ $# -ne 2 ]; then
      echo "Usage: encrypt-folder <source-folder> <encrypted-folder>"
      exit 1
    fi

    SOURCE="$1"
    ENCRYPTED="$2"

    if [ ! -d "$SOURCE" ]; then
      echo "Error: Source folder does not exist"
      exit 1
    fi

    mkdir -p "$ENCRYPTED"

    if [ -f "$ENCRYPTED/gocryptfs.conf" ] || find "$ENCRYPTED" -mindepth 1 -print -quit >/dev/null 2>&1; then
      echo "Error: Encrypted folder already initialised or non-empty"
      exit 1
    fi

    gocryptfs -init "$ENCRYPTED"
    MOUNT_POINT="/tmp/encrypt-mount-$$"
    mkdir -p "$MOUNT_POINT"

    cleanup() {
      if mountpoint -q "$MOUNT_POINT"; then
        fusermount -u "$MOUNT_POINT" || true
      fi
      rmdir "$MOUNT_POINT" 2>/dev/null || true
    }
    trap cleanup EXIT

    gocryptfs "$ENCRYPTED" "$MOUNT_POINT"
    rsync -av --progress "$SOURCE/" "$MOUNT_POINT/"
    trap - EXIT
    cleanup
  '';

  decryptFolder = pkgs.writeShellScriptBin "decrypt-folder" ''
    #!/usr/bin/env bash
    set -euo pipefail

    if [ $# -ne 2 ]; then
      echo "Usage: decrypt-folder <encrypted-folder> <mount-point>"
      exit 1
    fi

    ENCRYPTED="$1"
    MOUNT_POINT="$2"

    if [ ! -d "$ENCRYPTED" ]; then
      echo "Error: Encrypted folder does not exist"
      exit 1
    fi

    mkdir -p "$MOUNT_POINT"
    gocryptfs "$ENCRYPTED" "$MOUNT_POINT"
  '';

  mountNextcloud = pkgs.writeShellScriptBin "mount-nextcloud" ''
    #!/usr/bin/env bash
    set -euo pipefail
    if mountpoint -q /mnt/nextcloud; then
      echo "Nextcloud is already mounted"
      exit 0
    fi
    sudo mount /mnt/nextcloud
  '';

  umountNextcloud = pkgs.writeShellScriptBin "umount-nextcloud" ''
    #!/usr/bin/env bash
    set -euo pipefail
    if ! mountpoint -q /mnt/nextcloud; then
      exit 0
    fi
    sudo umount /mnt/nextcloud
  '';

  onedriveAuth = pkgs.writeShellScriptBin "onedrive-auth" ''
    #!/usr/bin/env bash
    set -euo pipefail
    sudo mkdir -p /var/lib/onedrive-auth
    sudo chown ${username}:users /var/lib/onedrive-auth
    sudo chmod 700 /var/lib/onedrive-auth
    if [ ! -f /var/lib/onedrive-auth/config ]; then
      sudo cp -r /etc/onedrive/* /var/lib/onedrive-auth/
      sudo chown -R ${username}:users /var/lib/onedrive-auth/
    fi
    onedrive --confdir /var/lib/onedrive-auth
  '';

  onedriveStatus = pkgs.writeShellScriptBin "onedrive-status" ''
    #!/usr/bin/env bash
    set -euo pipefail
    systemctl status onedrive-sync --no-pager
  '';

  umountOnedrive = pkgs.writeShellScriptBin "umount-onedrive" ''
    #!/usr/bin/env bash
    set -euo pipefail
    sudo systemctl stop onedrive-sync
  '';

  setupGdrive = pkgs.writeShellScriptBin "setup-gdrive" ''
    #!/usr/bin/env bash
    set -euo pipefail
    if rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
      echo "setup-gdrive: remote 'gdrive' already exists" >&2
      exit 1
    fi
    rclone config create gdrive drive scope drive
  '';

  mountGdrive = pkgs.writeShellScriptBin "mount-gdrive" ''
    #!/usr/bin/env bash
    set -euo pipefail
    if mountpoint -q /mnt/gdrive; then
      exit 0
    fi
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
  '';
in
{
  home.packages = with pkgs; [
    gocryptfs
    encfs
    cryptsetup
    encryptFolder
    decryptFolder
    mountNextcloud
    umountNextcloud
    onedriveAuth
    onedriveStatus
    umountOnedrive
    setupGdrive
    mountGdrive
  ];
}
