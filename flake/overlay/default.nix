{
  inputs,
  overlayLib,
  ...
}:
let
  customOverlays = import ./package { inherit inputs overlayLib; };
in
{
  nixpkgs.overlays = customOverlays;
}
