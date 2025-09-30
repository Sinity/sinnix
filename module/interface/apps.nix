# Desktop Applications and UI Components Configuration

{ pkgs, lib, ... }:
{
  config = {
    home-manager.users.sinity = {
      # === PACKAGES ===
      home.packages = with pkgs; [
        # --- From apps.nix ---
        junction
        libreoffice
        nautilus
        obsidian
        taskwarrior3
        timewarrior
        bleachbit
        transmission_3-gtk
        pulsemixer
        pwvucontrol
        bluetuith
        blueman
        evtest
        meld
        piper
        solaar
        android-tools
        android-file-transfer
        hledger
        llm
        single-file-cli
        programmer-calculator
        bc
        calc
        soundwireserver
        imgur-screenshot
        usbview
        strace
        ltrace
        nvitop
        cage
        wayland-protocols
        vkmark
        dtach
        lnch
        at
        yazi
        glow
        aria2

        # --- From clipboard.nix ---
        wl-clip-persist
        wl-clipboard
        clipse

        # --- From notifications.nix ---
        fnott
        libnotify
      ];

      # === SERVICES ===
      services = {
        # --- From clipboard.nix ---
        clipse = {
          enable = true;
          historySize = 99999;
          allowDuplicates = false;
          systemdTarget = "graphical-session.target";
          imageDisplay = {
            type = "kitty";
            scaleX = 9;
            scaleY = 9;
            heightCut = 2;
          };
          keyBindings = {
            choose = "enter";
            clearSelected = "D";
            down = "j";
            up = "k";
            end = "G";
            home = "g";
            filter = "/";
            more = "?";
            nextPage = "l";
            prevPage = "h";
            preview = "v";
            quit = "q";
            remove = "d";
            selectDown = "J";
            selectUp = "K";
            selectSingle = "V";
            togglePin = "m";
            togglePinned = "M";
            yankFilter = "y";
          };
        };

        # --- From notifications.nix ---
        fnott = {
          enable = true;
          settings = {
            main = {
              notification-margin = 8;
              anchor = "top-right";
              layer = "overlay";
              max-width = 400;
              max-height = 200;
              min-width = 300;
              border-size = 2;
              border-radius = 8;
              padding-horizontal = 12;
              padding-vertical = 8;
              progress-bar-height = 4;
            };
            low = {
              timeout = 5;
            };
            normal = {
              timeout = 10;
            };
            critical = {
              timeout = 0;
            };
          };
        };
      };

      # === PROGRAMS ===
      programs = {
        # --- From launcher.nix ---
        tofi = {
          enable = true;
          settings = {
            width = 2000;
            height = 1000;
            anchor = "center";
            horizontal = false;
            num-results = 0;
            result-spacing = 4;
            padding-top = 20;
            padding-bottom = 20;
            padding-left = 20;
            padding-right = 20;
            prompt-text = "> ";
            prompt-padding = 8;
            history = true;
            hide-cursor = true;
            text-cursor = true;
            matching-algorithm = "fuzzy";
            late-keyboard-init = false;
            multi-instance = false;
            terminal = "kitty";
          };
        };

        # --- From panel.nix ---
        waybar = {
          enable = true;
          systemd.enable = true;
          package = pkgs.waybar.overrideAttrs (oa: {
            mesonFlags = (oa.mesonFlags or [ ]) ++ [ "-Dexperimental=true" ];
          });
          style = lib.mkAfter ''
            * {
              font-family: "SauceCodePro Nerd Font Mono", monospace;
              font-weight: 600;
            }
            #waybar .modules-right > widget > * {
              margin: 0 8px;
            }
            #waybar .modules-right > widget:last-child > * {
              margin-right: 0;
            }
            #cpu { color: #fb4934; }
            #memory { color: #fabd2f; }
            #disk { color: #b8bb26; }
            #pulseaudio { color: #83a598; }
            #pulseaudio.muted { color: #665c54; }
          '';
          settings.mainBar = {
            position = "bottom";
            layer = "top";
            height = 30;
            margin-top = 0;
            margin-bottom = 0;
            margin-left = 0;
            margin-right = 0;
            modules-left = [
              "custom/launcher"
              "hyprland/workspaces"
              "tray"
            ];
            modules-center = [ "clock" ];
            modules-right = [
              "cpu"
              "memory"
              "disk"
              "pulseaudio"
              "custom/notification"
            ];
            clock = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󱑎</span> {:%H:%M}";
              tooltip = "true";
              tooltip-format = ''
                <big>{:%Y %B}</big>
                <tt><small>{calendar}</small></tt>'';
              format-alt = "<span font_family='SauceCodePro Nerd Font Mono'>󱑎</span> {:%d/%m}";
            };
            "hyprland/workspaces" = {
              active-only = false;
              disable-scroll = false;
              format = "{icon}";
              on-click = "activate";
              show-special = false;
              format-icons = {
                "1" = "I";
                "2" = "II";
                "3" = "III";
                "4" = "IV";
                "5" = "V";
                "active" = "󰮯";
                "default" = "󰊠";
                "special" = "󰠱";
                sort-by-number = true;
              };
              persistent-workspaces = {
                "1" = [ ];
                "2" = [ ];
                "3" = [ ];
                "4" = [ ];
                "5" = [ ];
              };
            };
            cpu = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󰍛</span> {usage}%";
              format-alt = "<span font_family='SauceCodePro Nerd Font Mono'>󰍛</span> {avg_frequency}GHz";
              interval = 2;
            };
            memory = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󰟜</span> {percentage}%";
              format-alt = "<span font_family='SauceCodePro Nerd Font Mono'>󰟜</span> {used}GB";
              interval = 2;
            };
            disk = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󰋊</span> {percentage_used}%";
              interval = 60;
            };
            tray = {
              icon-size = 20;
              spacing = 8;
            };
            pulseaudio = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󰕾</span> {volume}%";
              format-muted = "<span font_family='SauceCodePro Nerd Font Mono'>󰖁</span> MUTED";
              scroll-step = 5;
              on-click = "pamixer -t";
            };
            "custom/launcher" = {
              format = "<span font_family='SauceCodePro Nerd Font Mono'>󰀻</span>";
              on-click = "tofi-drun --drun-launch=true";
              tooltip = "false";
            };
            "custom/notification" = {
              tooltip = false;
              format = "{}";
              exec = "${pkgs.writeShellScript "notification-status" ''
                if ${pkgs.fnott}/bin/fnottctl list | grep -q .; then
                  echo \"<span font_family='SauceCodePro Nerd Font Mono'>󱅫</span>\"
                else
                  echo \"<span font_family='SauceCodePro Nerd Font Mono'>󰂚</span>\"
                fi
              ''}";
              interval = 1;
              on-click = "fnottctl dismiss";
              on-click-right = "fnottctl actions";
            };
          };
        };
      };

      # === XDG MIMES CONFIGURATION ===
      xdg = {
        configFile."mimeapps.list".force = true;
        mimeApps = {
          enable = true;
          associations.added = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "imv.desktop" ];
            "image/gif" = [ "imv.desktop" ];
            "image/jpeg" = [ "imv.desktop" ];
            "image/jpg" = [ "imv.desktop" ];
            "image/png" = [ "imv.desktop" ];
            "image/svg+xml" = [ "imv.desktop" ];
            "image/tiff" = [ "imv.desktop" ];
            "image/vnd.microsoft.icon" = [ "imv.desktop" ];
            "image/webp" = [ "imv.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "application/pdf" = [ "google-chrome-beta.desktop" ];
          };
          defaultApplications = {
            "text/plain" = [ "org.gnome.TextEditor.desktop" ];
            "image/bmp" = [ "imv.desktop" ];
            "image/gif" = [ "imv.desktop" ];
            "image/jpeg" = [ "imv.desktop" ];
            "image/jpg" = [ "imv.desktop" ];
            "image/png" = [ "imv.desktop" ];
            "image/svg+xml" = [ "imv.desktop" ];
            "image/tiff" = [ "imv.desktop" ];
            "image/vnd.microsoft.icon" = [ "imv.desktop" ];
            "image/webp" = [ "imv.desktop" ];
            "audio/aac" = [ "mpv.desktop" ];
            "audio/mpeg" = [ "mpv.desktop" ];
            "audio/ogg" = [ "mpv.desktop" ];
            "audio/opus" = [ "mpv.desktop" ];
            "audio/wav" = [ "mpv.desktop" ];
            "audio/webm" = [ "mpv.desktop" ];
            "video/mp4" = [ "mpv.desktop" ];
            "video/mkv" = [ "mpv.desktop" ];
            "video/webm" = [ "mpv.desktop" ];
            "video/x-matroska" = [ "mpv.desktop" ];
            "application/pdf" = [ "google-chrome-beta.desktop" ];
            "text/html" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/http" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/https" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/about" = [ "google-chrome-beta.desktop" ];
            "x-scheme-handler/unknown" = [ "google-chrome-beta.desktop" ];
          };
        };
      };
    };
  };
}
