{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "media"
  ];
  description = "Media playback and MPV tooling";
  configFn =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    let
      user = config.sinnix.user.name;
      inherit (config.sinnix.paths) capturesRoot;
      imvWithExtras =
        let
          sdl2ImageWithJxl = pkgs.SDL2_image.overrideAttrs (old: {
            buildInputs = old.buildInputs ++ [
              pkgs.libwebp
              pkgs.libjxl
            ];
          });
        in
        pkgs.imv.overrideAttrs (old: {
          buildInputs = old.buildInputs ++ [
            pkgs.libavif
            pkgs.libheif
            sdl2ImageWithJxl
          ];
          configureFlags = (old.configureFlags or [ ]) ++ [
            "--enable-all"
            "--with-backend=wayland"
          ];
        });
    in
    {
      home-manager.users.${user} =
        {
          pkgs,
          lib,
          config,
          ...
        }:
        let
          mpvBin = lib.getExe (config.programs.mpv.package or pkgs.mpv);
          fileBin = lib.getExe pkgs.file;
          pythonBin = lib.getExe pkgs.python3;
          systemXdgOpen = "/run/current-system/sw/bin/xdg-open";
        in
        {
          home = {
            sessionVariables = {
              MEDIA_DOMAIN = "v0.3";
              MPV_SCREENSHOT_DIR = "${capturesRoot}/screenshot/mpv";
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
              ffmpeg
              yt-dlp
              tdf
              zathura
              epy
              zotero
              gimp
              inkscape
              imvWithExtras
            ];
          };

          programs.mpv = {
            enable = true;
            config = {
              input-default-bindings = "no";
              profile = "normal";
              fs = true;
              force-window = "immediate";
              hwdec = "no";
              video-sync = "display-resample";
              audio-file-auto = "fuzzy";
              audio-pitch-correction = true;
              alang = "jp,jpn,en,eng,pl,pol";
              slang = "en,eng,pl,pol,jp,jpn";
              osd-level = 1;
              osd-duration = 2000;
              screenshot-format = "png";
              screenshot-png-compression = 9;
              screenshot-template = "${capturesRoot}/screenshot/mpv/%F-%P-%n";
              save-position-on-quit = true;
              resume-playback = "yes";
              hdr-compute-peak = false;
              sub-auto = "fuzzy";
              sub-file-paths = "sub:subs:subtitles";
              sub-font-size = 50;
            };

            profiles = {
              normal = {
                ytdl-format = "bestvideo[height<=?1440]+bestaudio/best";
                hr-seek-framedrop = "no";
                scale = "ewa_lanczossharp";
                cscale = "spline36";
                dscale = "mitchell";
                dither-depth = "auto";
                correct-downscaling = "yes";
                sigmoid-upscaling = "yes";
                deband = "yes";
              };
              wallpaper = {
                ytdl-format = "bestvideo[height<=?1440]+worstaudio/best";
                loop = "";
                osc = "no";
                audio = "no";
                input-ipc-server = "/tmp/mpvwallpapersocket";
                scale = "spline36";
                cscale = "spline36";
                dscale = "mitchell";
                dither-depth = "no";
                correct-downscaling = "no";
                sigmoid-upscaling = "no";
                deband = "no";
              };
              bench = {
                audio = "no";
                untimed = "yes";
                video-sync = "display-desync";
                opengl-swapinterval = "0";
              };
            };

            bindings = {
              "MBTN_LEFT" = "ignore";
              "MBTN_LEFT_DBL" = "cycle fullscreen";
              "MBTN_RIGHT" = "cycle pause";
              "WHEEL_UP" = "seek 10";
              "WHEEL_DOWN" = "seek -10";
              "l" = "seek 1 keyframes";
              "h" = "seek -1 keyframes";
              "Shift+l" = "no-osd seek 10 keyframes";
              "Shift+h" = "no-osd seek -10 keyframes";
              "ctrl+l" = "frame-step";
              "ctrl+h" = "frame-back-step";
              "alt+l" = "frame-step";
              "alt+h" = "frame-back-step";
              "j" = "add chapter 1";
              "k" = "add chapter -1";
              "shift+j" = "playlist-next";
              "shift+k" = "playlist-prev";
              "SPACE" = "cycle pause";
              "m" = "cycle mute";
              "f" = "cycle fullscreen";
              "ESC" = "set fullscreen no";
              "o" = "ab-loop";
              "i" = "script-binding stats/display-stats-toggle";
              "p" = "script-message osc-visibility auto";
              "P" = "script-message osc-visibility always";
              "v" = "vf toggle @fps_anime ; vf toggle @fps_film";
              "V" = "vf set \"\"";
              "q" = "quit";
              "Q" = "quit-watch-later";
              "ctrl+c" = "quit";
              "s" = "cycle sub";
              "S" = "cycle sub down";
              "a" = "cycle audio";
              "A" = "cycle audio down";
              "[" = "multiply speed 0.9091";
              "]" = "multiply speed 1.1";
              "{" = "multiply speed 0.5";
              "}" = "multiply speed 2.0";
              "BS" = "set speed 1.0";
              "alt+-" = "add sub-delay -0.1";
              "alt++" = "add sub-delay 0.1";
              "ctrl++" = "add audio-delay 0.100";
              "ctrl+-" = "add audio-delay -0.100";
              "z" = "add video-zoom 0.1";
              "Z" = "add video-zoom -0.1";
              "alt+BS" = "set video-zoom 0 ; set video-pan-x 0 ; set video-pan-y 0";
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
        };
    };
} args
