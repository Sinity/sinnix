# marimo 0.23.6 declares jedi < 0.20.0, but the current Python set carries
# jedi 0.20.0. Patch pyproject before wheel build so runtime dependency
# metadata matches the dependency set.
#
# recheck: when nixpkgs bumps marimo past 0.23.6 — check whether marimo's
# own jedi constraint has been widened upstream, making this substitution
# unnecessary (or requiring a new upper bound).
_: _final: prev: {
  pythonPackagesExtensions = (prev.pythonPackagesExtensions or [ ]) ++ [
    (_pyFinal: pyPrev: {
      marimo = pyPrev.marimo.overrideAttrs (old: {
        postPatch = (old.postPatch or "") + ''
          substituteInPlace pyproject.toml \
            --replace-fail '"jedi>=0.18.0,<0.20.0"' '"jedi>=0.18.0,<0.21.0"'
        '';
      });
    })
  ];
}
