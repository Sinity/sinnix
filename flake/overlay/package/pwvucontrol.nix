# Add patch to fix graceful format handling
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "pwvucontrol" [
  ../patch/pwvucontrol/graceful-format-missing-data.patch
]
