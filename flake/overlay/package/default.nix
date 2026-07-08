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
# - Any overlay that patches, disables tests in, or otherwise works around a
#   nixpkgs/upstream defect (as opposed to a permanent architecture choice —
#   e.g. chromium.nix's cache-hit engineering, or sinex.nix/polylogue.nix/
#   yt-polisher.nix re-exporting the project's own flake inputs) should carry
#   a `# recheck: <condition>` comment next to the workaround.
# - Format: `# recheck: <concrete, checkable condition>`, for example:
#     # recheck: when nixpkgs bumps foo past 1.2.3
#     # recheck: 2026-Q4
#     # recheck: when https://github.com/org/repo/issues/123 closes
#     # recheck: unknown — needs manual audit (state the open question)
# - A future overlay audit should `grep -rn '# recheck:' flake/overlay/package/`
#   and re-verify each condition: is the pinned version past the threshold,
#   has the linked issue closed, has the date passed? Drop the overlay (or
#   its workaround-specific piece) once the condition is satisfied, or update
#   the marker once re-verified as still needed.
# - Use `unknown — needs manual audit` only when a concrete condition
#   genuinely requires external research (checking an upstream issue tracker,
#   reading a diff) that hasn't been done yet — don't invent a plausible-
#   looking date or version just to fill the field. That marker is a tracked
#   gap for the next audit pass, not a dead end.
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
