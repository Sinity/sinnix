{ inputs, ... }:
final: _prev:
let
  system = final.stdenv.hostPlatform.system;
  cleanPkgs = import inputs.nixpkgs {
    inherit system;
    config = { }; # use upstream defaults to retain cache hits
    overlays = [ ];
  };
in
{
  # Use upstream chromium build to take advantage of Hydra caches.
  chromium-unwrapped = cleanPkgs.chromium-unwrapped;
  chromium = cleanPkgs.chromium;
}
