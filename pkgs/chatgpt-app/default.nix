# Upstream Linux packages rely on an external updater. Nix supplies the runtime;
# the launcher owns writable releases on /realm and checks at every launch.
{
  lib,
  pkgs,
  fetchurl,
  dpkg,
  curl,
  util-linux,
  coreutils,
  writeShellApplication,
  symlinkJoin,
  runCommand,
  ...
}:
let
  version = "26.928.31416";
  src = fetchurl {
    url = "https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_amd64.deb";
    hash = "sha256-xGNyfx7V3O14M4yOKmXYib0VMnb/Nz/XdpjMua8y0YE=";
  };
  libraries = with pkgs; [
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
  bootstrap = runCommand "chatgpt-bootstrap-${version}" { nativeBuildInputs = [ dpkg ]; } ''
    mkdir -p "$out"
    dpkg-deb --extract ${src} "$out"
  '';
  launcher = writeShellApplication {
    name = "chatgpt";
    runtimeInputs = [
      curl
      dpkg
      util-linux
      coreutils
    ];
    text = ''
      export NIX_LD=${pkgs.stdenv.cc.bintools.dynamicLinker}
      export NIX_LD_LIBRARY_PATH=${lib.makeLibraryPath libraries}
      export LD_LIBRARY_PATH="${lib.makeLibraryPath libraries}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      export XDG_DATA_DIRS="${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      state="''${CHATGPT_APP_HOME:-/realm/state/chatgpt-app}"
      mkdir -p "$state/releases"
      exec 9>"$state/update.lock"
      flock 9
      stage=$(mktemp -d "$state/.update-XXXXXXXX")
      trap 'rm -rf -- "$stage"' EXIT
      if [ ! -x "$state/current/ChatGPT" ]; then
        if [ ! -x "$state/releases/${version}/ChatGPT" ]; then
          cp -r ${bootstrap}/usr/lib/chatgpt "$stage/bootstrap"
          chmod -R u+w "$stage/bootstrap"
          mv "$stage/bootstrap" "$state/releases/${version}"
        fi
        ln -s "releases/${version}" "$stage/current"
        mv -Tf "$stage/current" "$state/current"
      fi
      # Upstream's Linux updater expects a package manager to replace the app.
      # Keep the bundle writable and replace its pointer only after validation.
      update_failed=0
      if curl --fail --location --silent --show-error --connect-timeout 10 --max-time 120 \
          --etag-compare "$state/etag" --etag-save "$stage/etag" \
          --output "$stage/latest.deb" \
          https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_amd64.deb; then
        if [ -s "$stage/latest.deb" ]; then
          if release=$(dpkg-deb --field "$stage/latest.deb" Version) && [[ "$release" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && \
              dpkg-deb --extract "$stage/latest.deb" "$stage/unpacked" && \
              [ -x "$stage/unpacked/usr/lib/chatgpt/ChatGPT" ] && \
              dpkg --compare-versions "$release" ge "$(basename "$(readlink "$state/current")")"; then
            if [ ! -d "$state/releases/$release" ]; then
              mv "$stage/unpacked/usr/lib/chatgpt" "$state/releases/$release"
            fi
            ln -s "releases/$release" "$stage/current"
            mv -Tf "$stage/current" "$state/current"
            mv "$stage/etag" "$state/etag"
            echo "ChatGPT updated to $release" >&2
          else
            update_failed=1
            echo "ChatGPT update rejected: invalid package; keeping installed release" >&2
          fi
        fi
      else
        update_failed=1
        echo "ChatGPT update failed; keeping installed release" >&2
      fi
      rm -rf -- "$stage"
      trap - EXIT
      flock -u 9
      exec 9>&-
      if [ "''${1:-}" = --update-only ]; then
        cat "$state/current/resources/linux-package-metadata.json"
        exit "$update_failed"
      fi
      proxy_args=()
      if [ -r /etc/sinnix/openai-proxy-url ]; then
        read -r proxy_url </etc/sinnix/openai-proxy-url
        proxy_args+=(--proxy-server="$proxy_url")
        export HTTP_PROXY="$proxy_url" HTTPS_PROXY="$proxy_url"
        export http_proxy="$proxy_url" https_proxy="$proxy_url"
        export NO_PROXY="127.0.0.1,localhost,::1" no_proxy="127.0.0.1,localhost,::1"
        export NODE_USE_ENV_PROXY=1
      fi
      exec "$state/current/ChatGPT" --ozone-platform=wayland "''${proxy_args[@]}" "$@"
    '';
  };
  desktop = runCommand "chatgpt-desktop" { } ''
    mkdir -p "$out/share/applications"
    cp ${bootstrap}/usr/share/applications/chatgpt.desktop "$out/share/applications/"
  '';
in
symlinkJoin {
  name = "chatgpt-${version}";
  paths = [
    launcher
    desktop
  ];
  postBuild = ''
    mkdir -p "$out/share/pixmaps"
    ln -s ${bootstrap}/usr/share/pixmaps/chatgpt.png "$out/share/pixmaps/chatgpt.png"
  '';
  meta = {
    description = "Official ChatGPT desktop app with automatic updates at launch";
    homepage = "https://developers.openai.com/codex/app";
    license = lib.licenses.unfree;
    mainProgram = "chatgpt";
    platforms = [ "x86_64-linux" ];
  };
}
