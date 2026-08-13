# Add patch to fix graceful format handling
#
# recheck: on any pwvucontrol version bump, re-diff
# ../patch/pwvucontrol/graceful-format-missing-data.patch against the new
# src/backend/pwnodeobject.rs. As of upstream tag 0.5.3 the three panicking
# .expect() calls ("Format id", "Channels int", "Rate int") and the
# single-node `return` this patch converts to `continue` are all still
# present verbatim, so the patch is fully load-bearing.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "pwvucontrol" [
  ../patch/pwvucontrol/graceful-format-missing-data.patch
]
