_: _final: prev: {
  xdg-desktop-portal-hyprland = prev.xdg-desktop-portal-hyprland.overrideAttrs (old: {
    buildInputs = (old.buildInputs or [ ]) ++ [ prev.libcap ];
  });
}
