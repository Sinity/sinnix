{
  lib,
  stdenv,
  fetchurl,
  dpkg,
  autoPatchelfHook,
  alsa-lib,
  at-spi2-atk,
  at-spi2-core,
  atk,
  cairo,
  cups,
  dbus,
  expat,
  fontconfig,
  gdk-pixbuf,
  glib,
  gtk3,
  libGL,
  libdrm,
  libgbm,
  libnotify,
  libpulseaudio,
  libusb1,
  libuuid,
  libx11,
  libxcb,
  libxcomposite,
  libxdamage,
  libxext,
  libxfixes,
  libxkbcommon,
  libxrandr,
  libxshmfence,
  mesa,
  nspr,
  nss,
  pango,
  pipewire,
  systemd,
  xdg-utils,
}:

stdenv.mkDerivation rec {
  pname = "chatgpt";
  version = "26.818.41705";

  # This is the official OpenAI Linux x86_64 download. The upstream endpoint
  # is intentionally pinned by hash; update both when OpenAI publishes a new
  # desktop release.
  src = fetchurl {
    url = "https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_amd64.deb";
    hash = "sha256-ySfJhVd73luszsx38C4UsxHZTmIwFWYh+vkleawDalU=";
  };

  nativeBuildInputs = [
    dpkg
    autoPatchelfHook
  ];

  # These are the NixOS equivalents of the shared-library dependencies in
  # OpenAI's Debian package. The application keeps its Electron/Chromium
  # payload bundled; autoPatchelfHook supplies the host-side ABI paths.
  buildInputs = [
    alsa-lib
    at-spi2-atk
    at-spi2-core
    atk
    cairo
    cups
    dbus
    expat
    fontconfig
    gdk-pixbuf
    glib
    gtk3
    libGL
    libdrm
    libgbm
    libnotify
    libpulseaudio
    stdenv.cc.cc
    libusb1
    libuuid
    libx11
    libxcb
    libxcomposite
    libxdamage
    libxext
    libxfixes
    libxkbcommon
    libxrandr
    libxshmfence
    mesa
    nspr
    nss
    pango
    pipewire
    systemd
    xdg-utils
  ];

  unpackPhase = ''
    runHook preUnpack
    mkdir source
    dpkg-deb --extract "$src" source
    cd source
    runHook postUnpack
  '';

  installPhase = ''
    mkdir -p "$out/lib" "$out/bin"
    cp -a usr/lib/chatgpt "$out/lib/"
    ln -s ../lib/chatgpt/codex-launcher "$out/bin/chatgpt"
    install -Dm644 usr/share/applications/chatgpt.desktop \
      "$out/share/applications/chatgpt.desktop"
    install -Dm644 usr/share/pixmaps/chatgpt.png \
      "$out/share/pixmaps/chatgpt.png"
  '';

  meta = {
    description = "Official ChatGPT and Codex desktop app from OpenAI";
    homepage = "https://developers.openai.com/codex/app";
    license = lib.licenses.unfree;
    mainProgram = "chatgpt";
    platforms = [ "x86_64-linux" ];
    sourceProvenance = with lib.sourceTypes; [ binaryNativeCode ];
  };
}
