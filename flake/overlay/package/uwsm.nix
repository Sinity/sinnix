# Fix systemd unit escaping in uwsm
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "uwsm" [
  ../patch/uwsm/fix-systemd-unit-escaping.patch
]
