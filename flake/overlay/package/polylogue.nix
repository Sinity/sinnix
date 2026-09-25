# Keep pytest's low-memory refusal and the status fallback while the pinned
# Polylogue source is built. Its raw-observation service and cursor-lag write
# leases are already upstream.
{ inputs, overlayLib }:
final: prev:
let
  imported = overlayLib.mkInputOverlay "polylogue" inputs.polylogue.packages final prev;
in
imported
// {
  polylogue = imported.polylogue.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./polylogue-pytest-admission.patch
      ./polylogue-status-document.patch
    ];
  });
}
