# Overlay DSL Helpers
#
# Common patterns for package overlays. Use these for simple cases;
# for complex custom logic, write a standard overlay instead.
#
# All helpers return overlay functions: final -> prev -> { ... }
#
# Usage in flake/overlay/package/*.nix:
#   { inputs }: inputs.self.lib.overlay.mkInputOverlay "polylogue" inputs.polylogue.packages
#   OR for helpers that don't need inputs:
#   _: _final: prev: { ... }  # continue with standard overlay
{ lib }:
rec {
  # Re-export a package from a flake input
  # Example: mkInputOverlay "polylogue" inputs.polylogue.packages
  mkInputOverlay = name: packages: _final: _prev: {
    ${name} = packages.${_final.stdenv.hostPlatform.system}.default;
  };

  # Apply patches to an existing package
  # Example: mkPatchOverlay "uwsm" [ ../patch/uwsm/fix.patch ]
  mkPatchOverlay = name: patches: _final: prev: {
    ${name} = prev.${name}.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ patches;
    });
  };

  # Add build inputs to an existing package
  # Example: mkBuildInputsOverlay "xdg-desktop-portal-hyprland" (pkgs: [ pkgs.libcap ])
  mkBuildInputsOverlay = name: buildInputsFn: _final: prev: {
    ${name} = prev.${name}.overrideAttrs (old: {
      buildInputs = (old.buildInputs or [ ]) ++ buildInputsFn prev;
    });
  };

}
