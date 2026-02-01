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
#
# Adding a new overlay:
# - Simply create a new .nix file in this directory
# - It will be auto-discovered and imported (no need to edit this file)
{ inputs, overlayLib }:
let
  mkOverlay = path: import path { inherit inputs overlayLib; };

  # Auto-discover all .nix files except default.nix
  overlayDir = builtins.readDir ./.;
  overlayNames = builtins.filter
    (name: name != "default.nix" && builtins.match ".*\\.nix$" name != null)
    (builtins.attrNames overlayDir);
in
builtins.map (name: mkOverlay ./${name}) overlayNames
