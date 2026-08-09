# python-discovery 1.4.2 has two stale assumptions under the pinned Python
# 3.14t interpreter: fallback discovery must re-propose one interpreter, and
# a free-threaded executable basename must satisfy a non-free-threaded spec.
# The package runtime remains unchanged; only those incompatible assertions are
# disabled until upstream updates them.
#
# recheck: when nixpkgs bumps python3Packages.python-discovery past 1.4.2 — retest with these tests enabled
_: _final: prev: {
  pythonPackagesExtensions = (prev.pythonPackagesExtensions or [ ]) ++ [
    (_pyFinal: pyPrev: {
      python-discovery = pyPrev.python-discovery.overrideAttrs (old: {
        disabledTests = (old.disabledTests or [ ]) ++ [
          "test_predicate_with_fallback_specs"
          "test_satisfies_path_not_abs_basename_match"
        ];
      });
    })
  ];
}
