# imv with additional format support (AVIF, HEIF, JXL)
#
# recheck: unknown — needs manual audit. As of nixpkgs' current imv (5.0.1,
# pkgs/by-name/im/imv/package.nix) this override is likely already stale:
# upstream imv moved to a meson build (`mesonFlags` + a `withBackends` list
# that already defaults to libjxl/libheif/libwebp on), has no `libavif`
# backend at all, and no longer depends on SDL2_image. The `configureFlags =
# [ "--enable-all" "--with-backend=wayland" ]` here are autotools-style
# flags that meson's configurePhase does not consume, and the extra
# buildInputs (libavif, libheif, the patched SDL2_image) are not referenced
# by imv's current build at all — so `imvWithExtras` (used by
# modules/features/desktop/media.nix) may currently provide zero benefit
# over plain `imv`. Needs a real build/format-support check against the
# live imv derivation to confirm, then either drop this overlay or rewrite
# it to pass `withBackends`/pull in a libavif backend the meson-based
# package actually understands.
_: _final: prev:
let
  sdl2ImageWithJxl = prev.SDL2_image.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [
      prev.libwebp
      prev.libjxl
    ];
  });
in
{
  imvWithExtras = prev.imv.overrideAttrs (old: {
    buildInputs = old.buildInputs ++ [
      prev.libavif
      prev.libheif
      sdl2ImageWithJxl
    ];
    configureFlags = (old.configureFlags or [ ]) ++ [
      "--enable-all"
      "--with-backend=wayland"
    ];
  });
}
