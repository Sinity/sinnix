# Media Domain Module
# Complete audio/video (system + applications)
# Consolidates: audio system, media players, production tools, viewers

{
  config,
  lib,
  pkgs,
  username,
  ...
}:
with lib;
{
  config = mkMerge [
    # System-level media configuration
    {
      # Domain identification
      system.nixos.tags = [ "media-domain-v0.3" ];

      # PipeWire audio system
      services.pipewire = {
        enable = true;
        audio.enable = true;
        alsa.enable = true;
        pulse.enable = true;
        # jack.enable = true;

        wireplumber = {
          enable = true;
          extraConfig = {
            "11-bluetooth-policy" = {
              "wireplumber.settings" = {
                "bluetooth.autoswitch-to-headset-profile" = false;
              };
            };
            "10-bluez" = {
              "monitor.bluez.properties" = {
                "bluez5.enable-sbc-xq" = true;
                "bluez5.enable-msbc" = true;
                "bluez5.enable-hw-volume" = true;
                "bluez5.roles" = [
                  "a2dp_sink"
                  "a2dp_source"
                ];
              };
            };
          };
        };
      };

      # Real-time audio optimizations
      systemd.user.services.pipewire.serviceConfig = {
        LimitRTPRIO = 95;
        LimitMEMLOCK = "infinity";
        Nice = -11;
        CPUSchedulingPolicy = "fifo";
        CPUSchedulingPriority = 90;
      };

      security.pam.loginLimits = [
        {
          domain = "@audio";
          type = "soft";
          item = "rtprio";
          value = "95";
        }
        {
          domain = "@audio";
          type = "hard";
          item = "rtprio";
          value = "95";
        }
        {
          domain = "@audio";
          type = "soft";
          item = "memlock";
          value = "unlimited";
        }
        {
          domain = "@audio";
          type = "hard";
          item = "memlock";
          value = "unlimited";
        }
      ];

      # System audio tools
      environment.systemPackages = with pkgs; [
        pulseaudioFull
        alsa-utils
        pavucontrol
        pamixer
        bluez
        playerctl # Media control
      ];

      # Audio group membership
      users.users.${username} = {
        extraGroups = [
          "audio"
          "bluetooth"
        ];
      };

      # Hardware-specific audio configuration should remain in host modules
      # This is for generic audio quantum forcing
      environment.etc."wireplumber/60-force-quantum.lua".text = ''
        rule = {
          matches = {
            { { "node.name", "matches", "alsa_output.usb-2cc2_*" }, },
          },
          apply_properties = { ["clock.force-quantum"] = 384 },
        }
        table.insert(alsa_monitor.rules, rule)
      '';
    }

    # User-level media configuration
    {
      home-manager.users.${username} = {
        # Media environment variables
        home = {
          sessionVariables = {
            MEDIA_DOMAIN = "v0.3";
            # Default screenshot directory
            MPV_SCREENSHOT_DIR = "$HOME/Pictures/mpv-screenshots";
          };

          # Media packages
          packages = with pkgs; [
            # Media players and libraries
            spotify
            mpv
            mpvc
            svp # SmoothVideo Project 4 (SVP4)
            vlc

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

            # Production tools
            audacity
            gimp
            inkscape
            # krita
            # blender
            # obs-studio

            # Enhanced image viewer with extended format support
            (
              let
                # Add libwebp & libjxl into SDL2_image
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
              })
            )
          ];
        };

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

        # Enhanced image viewer desktop entry
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
    }
  ];
}
