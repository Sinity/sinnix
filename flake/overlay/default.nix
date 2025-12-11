{
  inputs,
  ...
}:
let
  customOverlays = import ./package { inherit inputs; };
in
{
  nixpkgs.overlays = [
    inputs.sinex.overlays.default
    inputs.nix-vscode-extensions.overlays.default
  ]
  ++ customOverlays;
}
