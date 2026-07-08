# Fix systemd unit escaping in uwsm
#
# recheck: when nixpkgs bumps uwsm past 0.26.6 — upstream commit 643d38e
# ("fix: use escaped specifier in autoready and finalize, fixes #182",
# unreleased as of the 0.26.6 tag) fixes the same NoSuchUnit race via a
# different, root-cause approach: it stops reconstructing the unit name
# from an unescaped specifier and instead passes the already-correct unit
# object through, rather than catching the resulting DBusException. Once
# nixpkgs ships a uwsm release containing that commit, re-diff
# ../patch/uwsm/fix-systemd-unit-escaping.patch — it is likely redundant or
# needs reconciling with upstream's approach.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "uwsm" [
  ../patch/uwsm/fix-systemd-unit-escaping.patch
]
