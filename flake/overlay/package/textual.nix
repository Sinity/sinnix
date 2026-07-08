# textual 8.2.6 has sandbox-sensitive async UI tests under the current Python
# set. Keep downstream lynchpin/polylogue runtime environments buildable until
# nixpkgs or upstream refreshes the package.
#
# recheck: when nixpkgs bumps python3Packages.textual past 8.2.6 — retest
# with doCheck enabled; the async UI test sandbox-sensitivity may already be
# fixed upstream or nixpkgs may already disable the same tests itself.
_: _final: prev: {
  pythonPackagesExtensions = (prev.pythonPackagesExtensions or [ ]) ++ [
    (_pyFinal: pyPrev: {
      textual = pyPrev.textual.overrideAttrs (old: {
        doCheck = false;
      });
    })
  ];
}
