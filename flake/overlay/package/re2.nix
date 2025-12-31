{ inputs }: final: prev:
let
  inherit (final) lib;
  fixRe2 = drv:
    drv.overrideAttrs (old: {
      postFixup = lib.concatStringsSep "\n" [
        (old.postFixup or "")
        ''
          if [[ -n ''${dev:-} && -f "$dev/lib/cmake/re2/re2Config.cmake" ]]; then
            sed -i 's@set_and_check(re2_INCLUDE_DIR [^)]*)@set_and_check(re2_INCLUDE_DIR include)@' \
              "$dev/lib/cmake/re2/re2Config.cmake"
          fi
        ''
      ];
    });
in
{
  re2 = fixRe2 prev.re2;
}
