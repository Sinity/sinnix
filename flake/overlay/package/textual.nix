# textual 8.2.6 has sandbox-sensitive async UI tests under the current Python
# set. Keep downstream lynchpin/polylogue runtime environments buildable until
# nixpkgs or upstream refreshes the package.
_: _final: prev: {
  pythonPackagesExtensions = (prev.pythonPackagesExtensions or [ ]) ++ [
    (_pyFinal: pyPrev: {
      textual = pyPrev.textual.overrideAttrs (old: {
        doCheck = false;
      });
    })
  ];
}
