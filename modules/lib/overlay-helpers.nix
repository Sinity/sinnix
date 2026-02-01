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

  # Re-export with custom attribute path
  # Example: mkInputOverlayWith "codex" inputs.nix-ai-tools.packages (p: p.codex)
  mkInputOverlayWith = name: packages: selector: _final: _prev: {
    ${name} = selector packages.${_final.stdenv.hostPlatform.system};
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

  # Add native build inputs to an existing package
  # Example: mkNativeBuildInputsOverlay "foo" (pkgs: [ pkgs.cmake ])
  mkNativeBuildInputsOverlay = name: nativeBuildInputsFn: _final: prev: {
    ${name} = prev.${name}.overrideAttrs (old: {
      nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ nativeBuildInputsFn prev;
    });
  };

  # General attribute override
  # Example: mkOverrideAttrs "foo" (old: { doCheck = false; })
  mkOverrideAttrs = name: overrideFn: _final: prev: {
    ${name} = prev.${name}.overrideAttrs overrideFn;
  };

  # Combine multiple overlays for the same package
  # Example: mkComposedOverlay "foo" [
  #   (mkPatchOverlay "foo" [ ./fix.patch ])
  #   (mkBuildInputsOverlay "foo" (pkgs: [ pkgs.bar ]))
  # ]
  mkComposedOverlay = name: overlays: final: prev:
    let
      composed = lib.foldl' (acc: overlay:
        acc // (overlay final acc)
      ) prev overlays;
    in
    { ${name} = composed.${name}; };
}
