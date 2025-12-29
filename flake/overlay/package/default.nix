{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./bat.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./diffsitter.nix)
  (mkOverlay ./hyprland.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./uwsm.nix)
  (mkOverlay ./yt-dlp.nix)
]
