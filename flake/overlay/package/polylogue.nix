# Keep pytest's low-memory deferral while the pinned Polylogue source is
# built: upstream still floors the width at one worker (sinnix-do66), and
# polylogue-o5rjp moves the deferral upstream so this patch can go.
{ inputs, overlayLib }:
final: prev:
let
  imported = overlayLib.mkInputOverlay "polylogue" inputs.polylogue.packages final prev;
in
imported
// {
  polylogue = imported.polylogue.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./polylogue-pytest-admission.patch
    ];
  });
}
