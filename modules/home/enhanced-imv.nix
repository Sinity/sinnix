{pkgs, ...}: let
  # 1) Add libwebp & libjxl into SDL2_image
  sdl2ImageWithJxl = pkgs.SDL2_image.overrideAttrs (oldAttrs: {
    buildInputs =
      oldAttrs.buildInputs
      ++ [
        pkgs.libwebp
        pkgs.libjxl
      ];
  });

  # 2) Enhance imv itself: add all the extra inputs + configureFlags
  enhancedImv = pkgs.imv.overrideAttrs (oldAttrs: {
    buildInputs =
      oldAttrs.buildInputs
      ++ [
        pkgs.libavif
        pkgs.libheif
        sdl2ImageWithJxl
      ];
    configureFlags =
      (oldAttrs.configureFlags or [])
      ++ [
        "--enable-all"
        "--with-backend=wayland"
      ];
  });
in {
  # Install our custom imv
  home.packages = [
    enhancedImv
  ];

  # Create a desktop entry for it
  xdg.desktopEntries.imv = {
    name = "imv";
    genericName = "Image Viewer";
    comment = "Lightweight image viewer with extended format support";
    exec = "imv %F";
    terminal = false;
    categories = ["Graphics" "Viewer" "Photography"];
    mimeType = [
      "image/jpeg"
      "image/png"
      "image/gif"
      "image/webp"
      "image/avif"
      "image/heif"
      "image/heic"
      "image/jxl"
      "image/tiff"
      "image/bmp"
    ];
  };
}
