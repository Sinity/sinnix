# Add missing libcap dependency
#
# recheck: when nixpkgs bumps xdg-desktop-portal-hyprland past 1.3.12 —
# confirmed via upstream nixpkgs source that libcap is not in buildInputs at
# that version, so this override is still needed today. Re-verify against
# the new pinned version's buildInputs list before assuming it still is.
{ overlayLib, ... }:
overlayLib.mkBuildInputsOverlay "xdg-desktop-portal-hyprland" (pkgs: [ pkgs.libcap ])
