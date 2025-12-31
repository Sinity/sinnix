{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./bat.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./diffsitter.nix)
  (mkOverlay ./hyprland.nix)
  (mkOverlay ./perf-scan.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./re2.nix)
  (mkOverlay ./uwsm.nix)
  (mkOverlay ./xdg-desktop-portal-hyprland.nix)
  (mkOverlay ./yt-dlp.nix)
]
