# Nix-LD runtime for unpatched binaries
#
# Provides a dynamic linker and common shared libraries for running
# pre-compiled binaries (AppImages, proprietary software, etc.) that
# expect FHS-standard library paths.
#
# Enable with: sinnix.programs.nix-ld.enable = true
{ pkgs, lib, config, ... }:
let
  cfg = config.sinnix.programs.nix-ld;
in
{
  options.sinnix.programs.nix-ld.enable = lib.mkEnableOption "Nix-LD for running unpatched binaries";

  config = lib.mkIf cfg.enable {
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
        xorg.libX11
        xorg.libXScrnSaver
        xorg.libXcomposite
        xorg.libXcursor
        xorg.libXdamage
        xorg.libXext
        xorg.libXfixes
        xorg.libXi
        xorg.libXrandr
        xorg.libXrender
        xorg.libXtst
        xorg.libxcb
        xorg.libxkbfile
        xorg.libxshmfence
      ];
    };
  };
}
