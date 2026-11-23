{
  lib,
  stdenv,
  python3,
  qt6,
  cmake,
  pkg-config,
  mpv-unwrapped,
  ffmpeg,
  rankDesktopTools,
  makeDesktopItem,
  copyDesktopItems,
  sinnix-rank-core,
}:
let
  python = python3.withPackages (ps: [
    ps.pyside6
    sinnix-rank-core
  ]);
in
stdenv.mkDerivation {
  pname = "sinnix-rank-desktop";
  version = "0.1.0";
  src = lib.cleanSource ./.;
  nativeBuildInputs = [
    cmake
    pkg-config
    qt6.wrapQtAppsHook
    copyDesktopItems
  ];
  buildInputs = [
    qt6.qtdeclarative
    mpv-unwrapped
    qt6.qtbase
    qt6.qtwayland
  ];
  desktopItems = [
    (makeDesktopItem {
      name = "sinnix-rank-desktop";
      desktopName = "Compare";
      comment = "Compare videos, images and written options";
      exec = "sinnix-rank-desktop";
      icon = "view-preview";
      categories = [ "Utility" ];
    })
  ];
  # Every video opened spawns mpv decoder threads, and glibc keeps a malloc
  # arena per thread after it exits: idle memory grew about 80 MiB per pair
  # of videos opened and closed (390 MiB to 1 GiB over eight). Two arenas
  # hold it near 5 MiB per pair (2026-11-23, two 8K HEVC files, nvdec).
  postInstall = ''
    mkdir -p "$out/share/sinnix-rank" "$out/bin"
    cp "$src"/*.py "$src"/*.qml "$out/share/sinnix-rank/"
    mkdir -p "$out/share/sinnix-rank/shaders"
    shader="$out/share/sinnix-rank/shaders/perspective.frag.qsb"
    ${qt6.qtshadertools}/bin/qsb --glsl '100 es,300 es,120,150' \
      -o "$shader" "$src/shaders/perspective.frag"
    # qsb can report a write failure while exiting successfully.
    test -s "$shader"
    makeWrapper ${python}/bin/python3 "$out/bin/sinnix-rank-desktop" \
      --set LC_NUMERIC C \
      --set MALLOC_ARENA_MAX 2 \
      --suffix LD_LIBRARY_PATH : /run/opengl-driver/lib \
      --set QSG_RHI_BACKEND opengl \
      --prefix QML_IMPORT_PATH : "$out/lib/qt-6/qml" \
      --prefix PATH : ${lib.makeBinPath ([ ffmpeg ] ++ rankDesktopTools)} \
      --add-flags "$out/share/sinnix-rank/main.py" "''${qtWrapperArgs[@]}"
  '';
  dontWrapQtApps = true;
}
