# python-discovery 1.4.2 has stale assumptions under the pinned Python
# 3.14t interpreter. The current Polylogue package set carries the same
# workaround; keep the host package set aligned until nixpkgs updates it.
#
# recheck: when nixpkgs bumps python-discovery past 1.4.2, retest with checks enabled
_: _final: prev: {
  python314FreeThreading = prev.python314FreeThreading.override {
    packageOverrides = _pyFinal: pyPrev: {
      python-discovery = pyPrev.python-discovery.overrideAttrs (_old: {
        doCheck = false;
        doInstallCheck = false;
        installCheckInputs = [ ];
        nativeInstallCheckInputs = [ ];
      });
    };
  };
}
