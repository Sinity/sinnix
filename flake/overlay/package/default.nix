# ========================================
# OVERLAYS: Modify or extend nixpkgs
# ========================================
#
# Use overlays when:
# - Overriding existing nixpkgs packages (e.g., chromium with custom flags)
# - Patching upstream packages (e.g., aw-server-rust with fix)
# - Integrating external flake outputs into pkgs namespace
#
# Don't use overlays for:
# - Simple custom scripts → use flake/packages.nix instead
# - Standalone new packages → use flake/packages.nix instead
{ inputs }:
let
  mkOverlay = path: import path { inherit inputs; };
in
[
  (mkOverlay ./aw-server-rust.nix)
  (mkOverlay ./codex.nix)
  (mkOverlay ./chromium.nix)
  (mkOverlay ./polylogue.nix)
  (mkOverlay ./pwvucontrol.nix)
  (mkOverlay ./python.nix)
  (mkOverlay ./uwsm.nix)
  (mkOverlay ./xdg-desktop-portal-hyprland.nix)
]
