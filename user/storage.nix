{
  pkgs,
  ...
}:
let
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
  ];
}
