{ ... }:
final: prev:
let
  pname = "aionui";
  version = "1.4.2";
  src = final.fetchurl {
    url = "https://github.com/iOfficeAI/AionUi/releases/download/v${version}/AionUi-${version}-linux-x86_64.AppImage";
    hash = "sha256-7/eoVSyQoA9M3YUxlHRvvXBWeA0JelfHTupg98XzTus=";
  };
  appimageContents = final.appimageTools.extractType2 {
    inherit pname version src;
  };
in
{
  aionui = final.appimageTools.wrapType2 {
    inherit pname version src;
    nativeBuildInputs = [ final.makeWrapper ];
    extraPkgs =
      pkgs: with pkgs; [
        alsa-lib
        at-spi2-atk
        at-spi2-core
        bash
        brotli
        cairo
        cups
        curl
        dbus
        expat
        fontconfig
        freetype
        gdk-pixbuf
        glib
        glibc
        gsettings-desktop-schemas
        gtk3
        krb5
        libdrm
        libglvnd
        libnotify
        libpulseaudio
        libsecret
        libuuid
        libxkbcommon
        mesa
        nspr
        nss
        pango
        systemd
        util-linux
        wayland
        xdg-utils
        zlib
        xorg.libX11
        xorg.libXcomposite
        xorg.libXcursor
        xorg.libXdamage
        xorg.libXext
        xorg.libXfixes
        xorg.libXi
        xorg.libXrandr
        xorg.libxcb
      ];

    extraInstallCommands = ''
      wrapProgram "$out/bin/${pname}" \
        --set-default QT_QPA_PLATFORM xcb \
        --run 'if [ -n ''${WAYLAND_DISPLAY:-} ]; then
          set -- --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations --enable-wayland-ime "$@"
        fi' \
        --set-default ELECTRON_FORCE_IS_PACKAGED 1

      install -m 444 -D ${appimageContents}/AionUi.desktop $out/share/applications/AionUi.desktop
      install -m 444 -D ${appimageContents}/AionUi.png $out/share/icons/hicolor/512x512/apps/AionUi.png
      substituteInPlace $out/share/applications/AionUi.desktop \
        --replace-fail 'Exec=AppRun' 'Exec=${pname}'

      if [ -d ${appimageContents}/usr/share/icons ]; then
        mkdir -p $out/share
        cp -R ${appimageContents}/usr/share/icons $out/share/
      fi
    '';

    meta = with final.lib; {
      description = "Desktop interface for managing Aion CLI coding agents";
      homepage = "https://github.com/iOfficeAI/AionUi";
      license = licenses.asl20;
      platforms = [ "x86_64-linux" ];
      mainProgram = pname;
    };
  };
}
