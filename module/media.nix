# Media Domain Module
# Complete audio/video (system + applications)
# Consolidates: audio system, media players, production tools, viewers

{ pkgs, ... }:
{
  system.nixos.tags = [ "media-domain-v0.3" ];

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

  environment.systemPackages = with pkgs; [
    pulseaudioFull
    alsa-utils
    pavucontrol
    pamixer
    bluez
    playerctl # Media control
  ];

  users.users.sinity = {
    extraGroups = [
      "audio"
      "bluetooth"
    ];
  };

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

  home-manager.users.sinity = {
    home = {
      sessionVariables = {
        MEDIA_DOMAIN = "v0.3";
        MPV_SCREENSHOT_DIR = "$HOME/Pictures/mpv-screenshots";

        # Wine settings from environment.nix
        WINEDLLOVERRIDES = "winemenubuilder.exe=d"; # prevent wine from creating file associations
      };

      packages = with pkgs; [
        spotify
        ncspot # Terminal Spotify client
        mpv
        mpvc
        svp # SmoothVideo Project 4 (SVP4) vlc

        ani-cli
        trackma # Media tracking websites client
        fanficfare # Fanfiction downloader

        gpu-screen-recorder
        gpu-screen-recorder-gtk
        wf-recorder
        ffmpeg
        yt-dlp

        tdf # cli pdf viewer
        zathura
        epy # CLI Ebook Reader

        zotero # Research sources management

        audacity
        gimp
        inkscape
        # krita
        # blender
        # obs-studio

        # Gaming from desktop-apps.nix
        mangohud
        steam-run
        # steam-tui
        # protonup
        # bottles
        # Factorio with authentication token
        (factorio.override {
          username = "Sinityy";
          token = "$FACTORIO_TOKEN";
        })
        (pkgs.writeShellScriptBin "factorio-steam" ''
          exec ${steam-run}/bin/steam-run ${factorio}/bin/factorio "$@"
        '')

        # Hydrus with custom setup (from hydrus.nix)
        (pkgs.hydrus.overrideAttrs (oldAttrs: {
          doCheck = false;
          doInstallCheck = false;
          installPhase =
            oldAttrs.installPhase
            + ''
              mv $out/bin/hydrus-client $out/bin/hydrus-client-original
              cat > $out/bin/hydrus-client << EOF
              #!${pkgs.stdenv.shell}
              cd /realm/hydrus
              exec $out/bin/hydrus-client-original -d="/realm/hydrus/db" "\$@"
              EOF
              chmod +x $out/bin/hydrus-client
            '';
          preFixup = ''
            ${oldAttrs.preFixup or ""}
            makeWrapperArgs+=(--unset WAYLAND_DISPLAY --unset QT_QPA_PLATFORM)
          '';
        }))

        (
          let
            # Enhance SDL2_image with modern formats: WEBP and JPEG XL
            sdl2ImageWithJxl = pkgs.SDL2_image.overrideAttrs (oldAttrs: {
              buildInputs = oldAttrs.buildInputs ++ [
                pkgs.libwebp
                pkgs.libjxl
              ];
            });
          in
          # Enhanced imv with extended format support for AVIF, HEIF and JXL
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
        screenshot-template = "~/Pictures/mpv-screenshots/%F-%P-%n";

        save-position-on-quit = true;
        hdr-compute-peak = false;

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
  };
}
