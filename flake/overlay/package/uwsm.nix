_: _final: prev: {
  uwsm = prev.uwsm.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ../patch/uwsm/fix-systemd-unit-escaping.patch
    ];
  });
}
