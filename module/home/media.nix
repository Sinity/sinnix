{
  pkgs,
  config,
  lib,
  ...
}:
{
  # Media applications and utilities
  home.packages = with pkgs; [
    # Media players and libraries
    spotify
    mpv
    mpvc
    svp # SmoothVideo Project 4 (SVP4)

    # Media management tools
    ani-cli
    trackma # Media tracking websites client
    fanficfare # Fanfiction downloader

    # Media utilities
    gpu-screen-recorder
    gpu-screen-recorder-gtk
    wf-recorder
    ffmpeg
    yt-dlp

    # Document viewers
    tdf # cli pdf viewer
    zathura
    epy # CLI Ebook Reader

    # Library management
    zotero # Research sources management
  ];

  # MPV configuration
  programs.mpv = {
    enable = true;
    config = {
      # Video settings
      profile = "gpu-hq";
      scale = "ewa_lanczossharp";
      cscale = "ewa_lanczossharp";
      video-sync = "display-resample";
      interpolation = true;
      tscale = "oversample";

      # Audio settings
      audio-file-auto = "fuzzy";
      audio-pitch-correction = true;

      # Language preferences
      alang = "jpn,jp,eng,en,enUS,en-US";
      slang = "eng,en,und,enUS,en-US";

      # OSD settings
      osd-level = 1;
      osd-duration = 2000;

      # Screenshot settings
      screenshot-format = "png";
      screenshot-png-compression = 9;
      screenshot-template = "~/Pictures/mpv-screenshots/%F-%P-%n";

      # Playback
      save-position-on-quit = true;
      hdr-compute-peak = false;

      # Subtitle settings
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
}
