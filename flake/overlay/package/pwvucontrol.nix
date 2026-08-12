# Add patch to fix graceful format handling
#
# recheck: on any pwvucontrol version bump, re-diff
# ../patch/pwvucontrol/graceful-format-missing-data.patch against the new
# src/backend/pwnodeobject.rs. Verified against upstream tag 0.5.3
# (2026-08-12): the three panicking .expect() calls ("Format id",
# "Channels int", "Rate int") and the single-node `return` this patch
# converts to `continue` are all still present verbatim — an earlier
# version of this comment claimed upstream commit 2d7def3f fixed the base
# panic, which the 0.5.3 source refutes. The patch remains fully
# load-bearing.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "pwvucontrol" [
  ../patch/pwvucontrol/graceful-format-missing-data.patch
]
