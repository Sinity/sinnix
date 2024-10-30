{ config, lib, pkgs, ... }:

let
  mpv-with-vapoursynth = pkgs.mpv-unwrapped.wrapper {
    mpv = pkgs.mpv-unwrapped.override { vapoursynthSupport = true; };
    youtubeSupport = true;
    scripts = [ ];
  };
in
{
  imports = [];

  programs.mpv = {
    enable = true;
    package = pkgs.mpv; # mpv-with-vapoursynth;

    config = {
      # Disable default keybindings
      input-default-bindings = "no";

      # Default profile
      profile = "normal";

      # Start in fullscreen mode
      fs = "yes";

      # Display window immediately
      force-window = "immediate";

      # Disable hardware decoding
      hwdec = "no";

      # Video sync method
      video-sync = "display-resample";

      # Subtitle and audio language preferences
      slang = "en,eng,pl,pol,jp,jpn";
      alang = "jp,jpn,en,eng,pl,pol";

      # Enable resume playback
      resume-playback = "yes";

      # Subtitle appearance
      sub-font-size = "50";
      # sub-outline-width = "10";
    };

    # Profiles for different use cases
    profiles = {
      # Normal playback profile
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

      # Wallpaper mode profile
      wallpaper = {
        ytdl-format = "bestvideo[height<=?1440]+worstaudio/best";
        loop = "";
        osc = "no";
        no-audio = "";
        input-ipc-server = "/tmp/mpvwallpapersocket";
        scale = "spline36";
        cscale = "spline36";
        dscale = "mitchell";
        dither-depth = "no";
        correct-downscaling = "no";
        sigmoid-upscaling = "no";
        deband = "no";
      };

      # Benchmark profile
      bench = {
        audio = "no";
        untimed = "yes";
        video-sync = "display-desync";
        opengl-swapinterval = "0";
        # osd-msg1 = "FPS: ${estimated-display-fps}";
      };
    };

    # Custom key bindings
    bindings = {
      # Mouse controls
      MBTN_LEFT     = "ignore";
      MBTN_LEFT_DBL = "cycle fullscreen";
      MBTN_RIGHT    = "cycle pause";
      WHEEL_UP      = "seek 10";
      WHEEL_DOWN    = "seek -10";

      # Seeking controls
      l               = "seek 1 keyframes";
      h               = "seek -1 keyframes";
      "Shift+l"       = "no-osd seek 10 keyframes";
      "Shift+h"       = "no-osd seek -10 keyframes";
      "ctrl+l"        = "frame-step";
      "ctrl+h"        = "frame-back-step";
      "alt+l"         = "frame-step";
      "alt+h"         = "frame-back-step";

      # Chapter navigation
      j               = "add chapter 1";
      k               = "add chapter -1";

      # Playlist controls
      "shift+j"       = "playlist-next";
      "shift+k"       = "playlist-prev";

      # Playback controls
      "SPACE"         = "cycle pause";
      m               = "cycle mute";
      f               = "cycle fullscreen";
      "ESC"           = "set fullscreen no";
      o               = "ab-loop";
      i               = "script-binding stats/display-stats-toggle";
      p               = "script-message osc-visibility auto";
      P               = "script-message osc-visibility always";

      # Video filters
      v               = "vf toggle @fps_anime ; vf toggle @fps_film";
      V               = "vf set \"\"";

      # Quit controls
      q               = "quit";
      Q               = "quit-watch-later";
      "ctrl+c"        = "quit";

      # Subtitle and audio track cycling
      s               = "cycle sub";
      S               = "cycle sub down";
      a               = "cycle audio";
      A               = "cycle audio down";

      # Playback speed controls
      "["             = "multiply speed 0.9091";
      "]"             = "multiply speed 1.1";
      "{"             = "multiply speed 0.5";
      "}"             = "multiply speed 2.0";
      "BS"            = "set speed 1.0";

      # Subtitle sync
      "alt+-"         = "add sub-delay -0.1";
      "alt++"         = "add sub-delay +0.1";

      # Audio sync
      "ctrl++"        = "add audio-delay 0.100";
      "ctrl+-"        = "add audio-delay -0.100";

      # Video zoom and pan
      z               = "add video-zoom 0.1";
      Z               = "add video-zoom -0.1";
      "alt+BS"        = "set video-zoom 0 ; set video-pan-x 0 ; set video-pan-y 0";

      # Miscellaneous
      # e               = "show-text \"Edition: ${edition-list}\"";
    };
  };

  home.packages = with pkgs; [
    mediainfo
    vapoursynth
    aria2
    (pkgs.callPackage ../../pkgs/svpflow.nix {})
    ffmpeg
  ];

  # TODO: probably move this somewhere else
  programs.yt-dlp = {
    enable = true;
    settings = {
      downloader = "aria2c";
      downloader-args = "aria2c:'--max-concurrent-downloads 8 -s 16 -x 16 -k 1M'";
      geo-bypass = true;
      progress = true;
      sub-langs = "all";
      embed-subs = true;
      embed-thumbnail = true;
      embed-metadata = true;
      embed-chapters = true;
      embed-info-json = true;
      write-comments = true;
      sponsorblock-mark = "all";
      live-from-start = true;
      concurrent-fragments = 8;
      restrict-filenames = true;
      windows-filenames = true;
      remux-video = "mkv";
      merge-output-format = "mkv";
    };
  };
}
