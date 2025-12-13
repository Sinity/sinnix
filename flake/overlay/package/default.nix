{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./aider.nix)
  (mkOverlay ./aionui.nix)
  (mkOverlay ./bat.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./hyprland.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./uwsm.nix)
  (mkOverlay ./yt-dlp.nix)
]
