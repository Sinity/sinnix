# Re-export polylogue from flake input, then overlay-patch pin defects:
# undeclared raw_materialization_convergence start (sinnix-iqo6), pytest
# max(1) admission (sinnix-do66), and the status/write-lease hang that kept
# polylogued status from producing a document (sinnix-iqo6).
# recheck: when flake input polylogue is at or past 9238939f
{ inputs, overlayLib }:
final: prev:
let
  imported = overlayLib.mkInputOverlay "polylogue" inputs.polylogue.packages final prev;
in
imported
// {
  polylogue = imported.polylogue.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./polylogue-skip-undeclared-raw-materialization.patch
      ./polylogue-pytest-admission.patch
      ./polylogue-status-document.patch
    ];
  });
}
