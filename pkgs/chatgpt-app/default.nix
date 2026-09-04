{
  lib,
  stdenv,
  fetchurl,
  asar,
  dpkg,
  autoPatchelfHook,
  wrapGAppsHook3,
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
  gsettings-desktop-schemas,
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
  version = "26.901.41123";

  # This is the official OpenAI Linux x86_64 download. The upstream endpoint
  # is intentionally pinned by hash; update both when OpenAI publishes a new
  # desktop release.
  src = fetchurl {
    url = "https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_amd64.deb";
    hash = "sha256-C/eEeNVLDNDgsEy5yMabKyMbvAwm7Cgrylg2Qw2a1fY=";
  };

  nativeBuildInputs = [
    asar
    dpkg
    autoPatchelfHook
    wrapGAppsHook3
  ];

  # The upstream bundle ships optional Qt shims and musl/architecture
  # variants for hardware integrations. They are not loaded by the native
  # glibc Electron path on this system and are intentionally not Nix-patched.
  autoPatchelfIgnoreMissingDeps = [
    "libQt5Core.so.5"
    "libQt5Gui.so.5"
    "libQt5Widgets.so.5"
    "libQt6Core.so.6"
    "libQt6Gui.so.6"
    "libQt6Widgets.so.6"
    "libc.musl-x86_64.so.1"
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
    gsettings-desktop-schemas
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
    runHook preInstall

    mkdir -p "$out/lib" "$out/bin"
    cp -a usr/lib/chatgpt "$out/lib/"
    ln -s ../lib/chatgpt/codex-launcher "$out/bin/chatgpt"
    install -Dm644 usr/share/applications/chatgpt.desktop \
      "$out/share/applications/chatgpt.desktop"
    install -Dm644 usr/share/pixmaps/chatgpt.png \
      "$out/share/pixmaps/chatgpt.png"

    runHook postInstall
  '';

  preFixup = ''
    gappsWrapperArgs+=(
      --prefix LD_LIBRARY_PATH : ${lib.makeLibraryPath [ stdenv.cc.cc ]}
      --add-flags --ozone-platform=wayland
    )
  '';

  postInstall = ''
    asar extract "$out/lib/chatgpt/resources/app.asar" app-asar

    # fs.cp preserves the read-only modes of bundled files in the Nix store.
    # The app customizes those files in its staging directory before install.
    substituteInPlace app-asar/.vite/build/main-*.js \
      --replace-fail \
        'await y.default.cp(e,t,{recursive:!0,verbatimSymlinks:!0});return' \
        'await y.default.cp(e,t,{recursive:!0,verbatimSymlinks:!0});for(let e of await y.default.readdir(t,{recursive:!0,withFileTypes:!0})){if(e.isSymbolicLink())continue;let n=(0,p.join)(e.parentPath,e.name),r=await y.default.stat(n);await y.default.chmod(n,r.mode|128)}let n=await y.default.stat(t);await y.default.chmod(t,n.mode|128);return'

    rm "$out/lib/chatgpt/resources/app.asar"
    asar pack app-asar "$out/lib/chatgpt/resources/app.asar"
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
