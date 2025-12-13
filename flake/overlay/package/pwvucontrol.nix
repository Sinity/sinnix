{ ... }:
_final: prev: {
  pwvucontrol = prev.pwvucontrol.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ../patch/pwvucontrol/graceful-format-missing-data.patch
    ];
  });
}
