{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./lowdown.nix)
  (mkOverlay ./bat.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./diffsitter.nix)
  (mkOverlay ./chromium.nix)
  (mkOverlay ./perf-scan.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./re2.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./xdg-desktop-portal-hyprland.nix)
  (mkOverlay ./yt-dlp.nix)
]
