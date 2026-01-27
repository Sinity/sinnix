{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./aw-server-rust.nix)
  (mkOverlay ./lowdown.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./chromium.nix)
  (mkOverlay ./hogkill.nix)
  (mkOverlay ./perf-scan.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./re2.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./uwsm.nix)
  (mkOverlay ./xdg-desktop-portal-hyprland.nix)
]
