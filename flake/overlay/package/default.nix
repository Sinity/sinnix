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
#
# Overlay expiry — "# recheck:" convention:
# - Any overlay that works around a nixpkgs/upstream defect (as opposed to a
#   permanent architecture choice — e.g. chromium.nix's cache-hit
#   engineering, or sinex/polylogue/yt-polisher re-exporting the project's
#   own flake inputs) carries a `# recheck: <condition>` comment next to the
#   workaround.
# - Format: `# recheck: <concrete, checkable condition>`, for example:
#     # recheck: when nixpkgs bumps foo past 1.2.3
#     # recheck: 2026-Q4
#     # recheck: when https://github.com/org/repo/issues/123 closes
#     # recheck: unknown — needs manual audit (state the open question)
# - An audit pass greps `# recheck:` across this directory and re-verifies
#   each condition, dropping the workaround once satisfied.
# - Use `unknown — needs manual audit` only when the condition genuinely
#   requires external research; don't invent a plausible-looking date or
#   version to fill the field.
{ inputs, overlayLib }:
let
  mkOverlay = path: import path { inherit inputs overlayLib; };

  # Auto-discover all .nix files except default.nix
  overlayDir = builtins.readDir ./.;
  overlayNames = builtins.filter (
    name: name != "default.nix" && builtins.match ".*\\.nix$" name != null
  ) (builtins.attrNames overlayDir);
in
builtins.map (name: mkOverlay ./${name}) overlayNames
