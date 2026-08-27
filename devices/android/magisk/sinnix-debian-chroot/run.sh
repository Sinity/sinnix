#!/system/bin/sh
set -eu

ROOT="${0%/*}/rootfs"
BB=/data/adb/magisk/busybox

[ -x "$ROOT/bin/bash" ] || {
  echo "Debian rootfs is not installed" >&2
  exit 1
}

if [ "$#" -eq 0 ]; then
  set -- /bin/bash -l
fi

exec "$BB" unshare -m "$BB" sh -c '
  set -eu
  root=$1
  shift
  mount -o rprivate / /
  mount -t proc proc "$root/proc"
  mount -o rbind /dev "$root/dev"
  mount -o rslave "$root/dev" "$root/dev"
  mount -o rbind /sys "$root/sys"
  mount -o rslave "$root/sys" "$root/sys"
  exec chroot "$root" /usr/bin/env -i HOME=/root TERM="${TERM:-xterm-256color}" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
' sh "$ROOT" "$@"
