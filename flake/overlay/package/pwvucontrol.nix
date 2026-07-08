# Add patch to fix graceful format handling
#
# recheck: when nixpkgs bumps pwvucontrol past 0.5.2 — upstream already
# fixed the base `.expect("Format!")` panic in commit 2d7def3f ("Remove
# expects from update_format", 2026-02-13), which shipped in the 0.5.2
# release; a newer 0.5.3 tag exists upstream too. Our patch builds on top of
# that fix by turning the single-node `return` into `continue` inside what
# looks like a multi-node update loop (so one node's bad/missing format
# doesn't abort processing the rest) and adds node id/name to the warning.
# Re-diff ../patch/pwvucontrol/graceful-format-missing-data.patch against
# whatever pwvucontrol version nixpkgs ships next — the base panic fix is
# now upstream, but the return-vs-continue behavior may still need this
# patch, or may have been separately fixed too.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "pwvucontrol" [
  ../patch/pwvucontrol/graceful-format-missing-data.patch
]
