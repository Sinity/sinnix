{ inputs, ... }: final: prev:
let
  inherit (final) lib;
  fixRe2 =
    drv:
    drv.overrideAttrs (old: {
      postInstall = lib.concatStringsSep "\n" [
        (old.postInstall or "")
        ''
          patch_re2_config() {
            local file="$1"
            if [[ ! -f "$file" ]]; then
              return
            fi

            tmp="$(mktemp)"
            awk '
              /^set_and_check\(re2_INCLUDE_DIR/ {next}
              /^include\(CMakeFindDependencyMacro\)$/ {
                print
                print ""
                print "set_and_check(re2_INCLUDE_DIR ''${PACKAGE_PREFIX_DIR}/include)"
                next
              }
              {print}
            ' "$file" > "$tmp"
            mv "$tmp" "$file"
          }

          patch_re2_config "$out/lib/cmake/re2/re2Config.cmake"
          if [[ -n "$dev" ]]; then
            patch_re2_config "$dev/lib/cmake/re2/re2Config.cmake"
          fi
        ''
      ];
    });
in
{
  re2 = fixRe2 prev.re2;
}
