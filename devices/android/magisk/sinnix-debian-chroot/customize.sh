SKIPMOUNT=true

ui_print "- Extracting Debian arm64 root filesystem"
mkdir -p "$MODPATH/rootfs"
tar -xzf "$MODPATH/rootfs.tar.gz" -C "$MODPATH/rootfs"
rm "$MODPATH/rootfs.tar.gz"
cp "$MODPATH/resolv.conf" "$MODPATH/rootfs/etc/resolv.conf"
rm "$MODPATH/resolv.conf"
set_perm_recursive "$MODPATH" 0 0 0755 0755
set_perm "$MODPATH/rootfs/tmp" 0 0 01777
set_perm "$MODPATH/run.sh" 0 0 0755
