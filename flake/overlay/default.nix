{
  inputs,
  ...
}:
let
  customOverlays = import ./package { inherit inputs; };
in
{
  nixpkgs.overlays = [
    inputs.nix-vscode-extensions.overlays.default
  ]
  ++ customOverlays;
}
