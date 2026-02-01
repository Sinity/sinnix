# Add missing libcap dependency
{ overlayLib, ... }:
overlayLib.mkBuildInputsOverlay "xdg-desktop-portal-hyprland" (pkgs: [ pkgs.libcap ])
