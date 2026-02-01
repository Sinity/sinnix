{
  inputs,
  overlayLib,
  ...
}:
let
  customOverlays = import ./package { inherit inputs overlayLib; };
in
{
  nixpkgs.overlays = [
    inputs.nix-vscode-extensions.overlays.default
  ]
  ++ customOverlays;
}
