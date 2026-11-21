{
  lib,
  stdenvNoCC,
  python3,
  qt6,
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
stdenvNoCC.mkDerivation {
  pname = "sinnix-rank-desktop";
  version = "0.1.0";
  src = lib.cleanSource ./.;
  nativeBuildInputs = [
    qt6.wrapQtAppsHook
    copyDesktopItems
  ];
  buildInputs = [
    qt6.qtdeclarative
    qt6.qtmultimedia
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
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/sinnix-rank" "$out/bin"
    cp -r . "$out/share/sinnix-rank/"
    for shader in "$out/share/sinnix-rank"/shaders/*.frag; do
      ${qt6.qtshadertools}/bin/qsb --glsl '100 es,300 es,120,150' -o "$shader.qsb" "$shader"
    done
    makeWrapper ${python}/bin/python3 "$out/bin/sinnix-rank-desktop" \
      --set-default QSG_RHI_BACKEND opengl \
      --prefix PATH : ${lib.makeBinPath ([ ffmpeg ] ++ rankDesktopTools)} \
      --add-flags "$out/share/sinnix-rank/main.py" "''${qtWrapperArgs[@]}"
    runHook postInstall
  '';
  dontWrapQtApps = true;
}
