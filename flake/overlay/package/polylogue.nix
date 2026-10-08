# Re-export the pinned upstream package without local implementation patches.
{ inputs, overlayLib }:
final: prev: overlayLib.mkInputOverlay "polylogue" inputs.polylogue.packages final prev
