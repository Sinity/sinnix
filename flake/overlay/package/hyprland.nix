_: _final: prev:
let
  hyprlandPatches = builtins.path {
    path = ../patch/hyprland;
    name = "sinnix-hyprland-patches";
  };
  hyprlandPatch = name: hyprlandPatches + "/${name}";
in
{
  hyprland = prev.hyprland.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      (hyprlandPatch "suppress-color-warning.patch")
      (hyprlandPatch "check-monitor-null.patch")
      (hyprlandPatch "special-workspace-damage.patch")
      (hyprlandPatch "guard-last-monitor.patch")
    ];
  });
}
