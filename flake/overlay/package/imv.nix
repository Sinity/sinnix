# imv with additional format support (AVIF, HEIF, JXL)
{ inputs, ... }: final: prev:
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
