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
  postInstall = ''
    mkdir -p "$out/share/sinnix-rank" "$out/bin"
    cp "$src"/*.py "$src"/*.qml "$out/share/sinnix-rank/"
    cp -r "$src/shaders" "$out/share/sinnix-rank/"
    for shader in "$out/share/sinnix-rank"/shaders/*.frag; do
      ${qt6.qtshadertools}/bin/qsb --glsl '100 es,300 es,120,150' -o "$shader.qsb" "$shader"
    done
    makeWrapper ${python}/bin/python3 "$out/bin/sinnix-rank-desktop" \
      --set LC_NUMERIC C \
      --suffix LD_LIBRARY_PATH : /run/opengl-driver/lib \
      --set QSG_RHI_BACKEND opengl \
      --prefix QML_IMPORT_PATH : "$out/lib/qt-6/qml" \
      --prefix PATH : ${lib.makeBinPath ([ ffmpeg ] ++ rankDesktopTools)} \
      --add-flags "$out/share/sinnix-rank/main.py" "''${qtWrapperArgs[@]}"
  '';
  dontWrapQtApps = true;
}
