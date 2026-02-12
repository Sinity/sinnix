# Nix-LD runtime for unpatched binaries
#
# Provides a dynamic linker and common shared libraries for running
# pre-compiled binaries (AppImages, proprietary software, etc.) that
# expect FHS-standard library paths.
{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [
    "system"
    "nix-ld"
  ];
  description = "Nix-LD for running unpatched binaries";
  configFn =
    { pkgs, ... }:
    {
      programs.nix-ld = {
        enable = true;
        libraries = with pkgs; [
          stdenv.cc.cc
          openssl
          curl
          glib
          util-linux
          glibc
          icu
          libunwind
          libuuid
          zlib
          libsecret
          freetype
          libglvnd
          libnotify
          SDL2
          vulkan-loader
          gdk-pixbuf
          pipewire
          pulseaudio
          alsa-lib
          at-spi2-atk
          at-spi2-core
          atk
          cairo
          cups
          dbus
          expat
          fontconfig
          fuse3
          gtk3
          libGL
          libappindicator-gtk3
          libdrm
          libpulseaudio
          nspr
          nss
          pango
          systemd
          libx11
          libxscrnsaver
          libxcomposite
          libxcursor
          libxdamage
          libxext
          libxfixes
          libxi
          libxrandr
          libxrender
          libxtst
          libxcb
          libxkbfile
          libxshmfence
        ];
      };
    };
} args
