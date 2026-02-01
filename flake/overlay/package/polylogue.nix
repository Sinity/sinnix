# Re-export polylogue from flake input
{ inputs, overlayLib }:
overlayLib.mkInputOverlay "polylogue" inputs.polylogue.packages
