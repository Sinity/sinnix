{
  pkgs,
  config,
  sinnix,
  lib,
  ...
}:
let
  homeRoot = config.home.homeDirectory;
  inherit (sinnix.paths) dataRoot;
  hydrusProfileDir = "${homeRoot}/.hydrus";

  hydrusWithProfile = pkgs.hydrus.overrideAttrs (oldAttrs: {
    doCheck = false;
    doInstallCheck = false;
    installPhase = oldAttrs.installPhase + ''
      mv $out/bin/hydrus-client $out/bin/hydrus-client-original
      cat > $out/bin/hydrus-client << EOF
      #!${pkgs.stdenv.shell}
      cd ${hydrusProfileDir}
      exec $out/bin/hydrus-client-original -d="${hydrusProfileDir}/db" "\$@"
      EOF
      chmod +x $out/bin/hydrus-client
    '';
    preFixup = ''
      ${oldAttrs.preFixup or ""}
      makeWrapperArgs+=(--unset WAYLAND_DISPLAY --unset QT_QPA_PLATFORM)
    '';
  });

  imvWithExtras =
    let
      sdl2ImageWithJxl = pkgs.SDL2_image.overrideAttrs (oldAttrs: {
        buildInputs = oldAttrs.buildInputs ++ [
          pkgs.libwebp
          pkgs.libjxl
        ];
      });
    in
    pkgs.imv.overrideAttrs (oldAttrs: {
      buildInputs = oldAttrs.buildInputs ++ [
        pkgs.libavif
        pkgs.libheif
        sdl2ImageWithJxl
      ];
      configureFlags = (oldAttrs.configureFlags or [ ]) ++ [
        "--enable-all"
        "--with-backend=wayland"
      ];
    });
in
{
  home = {
    sessionVariables = {
      MEDIA_DOMAIN = "v0.3";
      MPV_SCREENSHOT_DIR = "${dataRoot}/screenshot/mpv";
      WINEDLLOVERRIDES = "winemenubuilder.exe=d";
    };

    packages = with pkgs; [
      spotify
      ncspot
      mpvc
      svp
      ani-cli
      trackma
      fanficfare
      gpu-screen-recorder
      gpu-screen-recorder-gtk
      wf-recorder
      ffmpeg
      yt-dlp
      tdf
      zathura
      epy
      zotero
      gimp
      inkscape
      mangohud
      steam-run
      hydrusWithProfile
      imvWithExtras
    ];

    activation.ensureHydrusProfile = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      install -d -m700 "${hydrusProfileDir}"
      install -d -m700 "${hydrusProfileDir}/db"
    '';
  };

  programs.mpv = {
    enable = true;
    config = {
      profile = "gpu-hq";
      scale = "ewa_lanczossharp";
      cscale = "ewa_lanczossharp";
      video-sync = "display-resample";
      interpolation = true;
      tscale = "oversample";

      audio-file-auto = "fuzzy";
      audio-pitch-correction = true;

      alang = "jpn,jp,eng,en,enUS,en-US";
      slang = "eng,en,und,enUS,en-US";

      osd-level = 1;
      osd-duration = 2000;

      screenshot-format = "png";
      screenshot-png-compression = 9;
      screenshot-template = "${dataRoot}/screenshot/mpv/%F-%P-%n";

      save-position-on-quit = true;
      hdr-compute-peak = true;

      sub-auto = "fuzzy";
      sub-file-paths = "sub:subs:subtitles";
    };

    bindings = {
      "WHEEL_UP" = "add volume 2";
      "WHEEL_DOWN" = "add volume -2";
      "l" = "seek 5";
      "h" = "seek -5";
      "j" = "seek -60";
      "k" = "seek 60";
      "S" = "screenshot subtitles";
      "s" = "screenshot";
    };
  };

  xdg.desktopEntries.imv = {
    name = "imv";
    genericName = "Image Viewer";
    comment = "Lightweight image viewer with extended format support";
    exec = "imv %F";
    terminal = false;
    categories = [
      "Graphics"
      "Viewer"
      "Photography"
    ];
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
