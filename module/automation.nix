# Automation Domain Module
# Complete orchestration (services + scripts)
# Consolidates: scripts, services, monitoring, scheduling

{ pkgs, ... }:
let
  # Scripts inlined from module/home/scripts/scripts/*
  wall-change = pkgs.writeShellScriptBin "wall-change" ''
    #!/usr/bin/env bash
    DIR="$HOME/pic/wallpaper"
    PICS=($(find "$DIR" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.gif" \)))
    RANDOMPICS="''${PICS[ $RANDOM % ''${#PICS[@]} ]}"
    ${pkgs.swaybg}/bin/swaybg -m fill -i "$RANDOMPICS"
  '';

  wallpaper-picker = pkgs.writeShellScriptBin "wallpaper-picker" ''
    #!/usr/bin/env bash
    DIR="$HOME/pic/wallpaper"
    cd "$DIR"
    selected=$(find . -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.gif" \) | sed 's|\./||' | rofi -dmenu -p "🖼️")
    if [[ -n "$selected" ]]; then
        ${pkgs.swaybg}/bin/swaybg -m fill -i "$DIR/$selected" &
    fi
  '';

  runbg = pkgs.writeShellScriptBin "runbg" ''
    #!/usr/bin/env bash
    $@ &
    disown
  '';

  lofi = pkgs.writeScriptBin "lofi" ''
    #!/usr/bin/env bash
    ${pkgs.libnotify}/bin/notify-send "起動 Lofi Music" "Enjoy!"
    ${pkgs.mpv}/bin/mpv "https://www.youtube.com/watch?v=jfKfPfyJRdk" --no-video --loop-playlist=inf
  '';

  toggle_blur = pkgs.writeScriptBin "toggle_blur" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:blur:enabled | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "1" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled false
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled true
    fi
  '';

  toggle_opacity = pkgs.writeScriptBin "toggle_opacity" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:inactive_opacity | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "0.900000" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 1.0
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 0.9
    fi
  '';

  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x "waybar" > /dev/null; then
        ${pkgs.procps}/bin/pkill waybar
    else
        ${pkgs.waybar}/bin/waybar &
    fi
  '';

  maxfetch = pkgs.writeScriptBin "maxfetch" ''
    #!/usr/bin/env bash
    echo "System Information:"
    echo "OS: $(${pkgs.coreutils}/bin/uname -o)"
    echo "Kernel: $(${pkgs.coreutils}/bin/uname -r)"
    echo "Uptime: $(${pkgs.procps}/bin/uptime -p)"
    echo "Shell: $SHELL"
  '';

  compress = pkgs.writeScriptBin "compress" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: compress <file_or_directory> [output_name]"
        exit 1
    fi

    INPUT="$1"
    OUTPUT="$2"

    if [ -z "$OUTPUT" ]; then
        OUTPUT="$(${pkgs.coreutils}/bin/basename "$INPUT").tar.gz"
    fi

    ${pkgs.gnutar}/bin/tar -czf "$OUTPUT" "$INPUT"
    echo "Compressed $INPUT to $OUTPUT"
  '';

  extract = pkgs.writeScriptBin "extract" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: extract <file>"
        exit 1
    fi

    case "$1" in
        *.tar.gz|*.tgz) ${pkgs.gnutar}/bin/tar -xzf "$1" ;;
        *.tar.bz2|*.tbz2) ${pkgs.gnutar}/bin/tar -xjf "$1" ;;
        *.tar) ${pkgs.gnutar}/bin/tar -xf "$1" ;;
        *.zip) ${pkgs.unzip}/bin/unzip "$1" ;;
        *.rar) ${pkgs.unrar}/bin/unrar x "$1" ;;
        *.7z) ${pkgs.p7zip}/bin/7z x "$1" ;;
        *) echo "Unsupported format: $1" ;;
    esac
  '';

  shutdown-script = pkgs.writeScriptBin "shutdown-script" ''
    #!/usr/bin/env bash
    ${pkgs.systemd}/bin/systemctl poweroff
  '';

  show-keybinds = pkgs.writeScriptBin "show-keybinds" ''
    #!/usr/bin/env bash
    ${pkgs.rofi-wayland}/bin/rofi -dmenu -p "Keybinds" <<EOF
    SUPER + Return: Open terminal
    SUPER + D: Application launcher
    SUPER + Q: Close window
    SUPER + F: Fullscreen
    SUPER + Space: Toggle floating
    EOF
  '';

  ascii = pkgs.writeScriptBin "ascii" ''
    #!/usr/bin/env bash
    echo "    ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄"
    echo "    ██ ▄▄▄▄▄ █▀▄▀█ ▄▄▄▄▄ ██ ▄▄▄▄▄ █ ▄▄▀█ ▄▄▄▄ █ ▄▄▄▄▄ █"
    echo "    ██ █████ █ █▀█ █████ ██ █████ █ ██ █ ████ █ █████ █"
    echo "    ██▄▄▄▄▄▄▄█▄▄▄█▄▄▄▄▄▄▄██▄▄▄▄▄▄▄█▄██▄█▄▄▄▄▄▄█▄▄▄▄▄▄▄█"
  '';

  record = pkgs.writeScriptBin "record" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x "wl-screenrec" > /dev/null; then
        ${pkgs.procps}/bin/pkill wl-screenrec
        ${pkgs.libnotify}/bin/notify-send "Recording stopped"
    else
        ${pkgs.wl-screenrec}/bin/wl-screenrec -f "/realm/inbox/recording_$(${pkgs.coreutils}/bin/date +'%Y-%m-%d_%H-%M-%S').mp4" &
        ${pkgs.libnotify}/bin/notify-send "Recording started"
    fi
  '';

  rofi-power-menu = pkgs.writeScriptBin "rofi-power-menu" ''
    #!/usr/bin/env bash
    options="Shutdown\nReboot\nSuspend\nLogout"
    selected=$(echo -e "$options" | ${pkgs.rofi-wayland}/bin/rofi -dmenu -p "Power Menu")

    case "$selected" in
        "Shutdown") ${pkgs.systemd}/bin/systemctl poweroff ;;
        "Reboot") ${pkgs.systemd}/bin/systemctl reboot ;;
        "Suspend") ${pkgs.systemd}/bin/systemctl suspend ;;
        "Logout") ${pkgs.hyprland}/bin/hyprctl dispatch exit ;;
    esac
  '';

  power-menu = pkgs.writeScriptBin "power-menu" ''
    #!/usr/bin/env bash
    rofi-power-menu
  '';

  vm-start = pkgs.writeShellScriptBin "vm-start" ''
    # VM name
    vm_name="win10"
    export LIBVIRT_DEFAULT_URI="qemu:///system"

    # change workspace
    ${pkgs.hyprland}/bin/hyprctl dispatch workspace 6

    ${pkgs.libvirt}/bin/virsh start "$vm_name"
    ${pkgs.virt-viewer}/bin/virt-viewer -f -w -a "$vm_name"
  '';

  # ASBL mitigation script
  asbl-fooler = pkgs.writeShellApplication {
    name = "asbl-no-moar";
    runtimeInputs = [
      pkgs.wl-gammactl
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      echo "Setting gamma to 1.2"
      timeout -p 3500ms ${pkgs.wl-gammactl}/bin/wl-gammactl -g 1.2 || true
      echo "Gamma is back to 1.0"
    '';
  };
in
{
  system.nixos.tags = [ "automation-domain-v0.3" ];

  services = {

    transmission = {
      enable = true;
      settings = {
        script-torrent-done-enabled = false;
        ratio-limit-enabled = false;
        umask = 18; # 002
        download-dir = "/outer-realm/inbox";
        incomplete-dir-enabled = false;
        rpc-port = 9091;
      };
    };

    ollama = {
      enable = true;
      acceleration = "cuda";
    };

    # Monero service (commented out for easy enablement)
    # monero = {
    #   enable = true;
    #   dataDir = "/var/lib/monero";
    # };
  };

  home-manager.users.sinity = {
    home.packages = with pkgs; [
      wall-change
      wallpaper-picker
      vm-start

      runbg
      lofi

      toggle_blur
      toggle_opacity
      toggle_waybar

      # System information
      maxfetch

      # File management automation
      compress
      extract

      # Power management
      shutdown-script
      power-menu
      rofi-power-menu

      # Documentation and help
      show-keybinds
      ascii

      # Media recording
      record

      # ASBL mitigation
      asbl-fooler

      # From home/system.nix - system monitoring
      btop
      ncdu # disk space
      nitch # system fetch util

      # From home/system.nix - CLI utilities
      toipe # typing test in the terminal
      ttyper # cli typing test

      # From home/system.nix - Terminal toys
      cbonsai
      pipes
      tty-clock

      # From home/system.nix - Graphics tools
      mesa-demos
      vulkan-tools
      vulkan-validation-layers
      wayland-utils
      libva-utils
      glxinfo
      drm_info

      # Script dependencies
      unzip # For extract.sh
      unrar # For extract.sh
      p7zip # For extract.sh
      zenity # For record.sh dialogs
      rofi-wayland # For various scripts (wallpaper-picker, show-keybinds)

      # VM management dependencies (for vm-start)
      virt-viewer
      libvirt

      # ActivityWatch watchers
      aw-watcher-window-wayland
      aw-watcher-afk
    ];

    # Activity monitoring and tracking
    # From home/system.nix - btop configuration
    programs.btop = {
      enable = true;
      settings = {
        color_theme = "gruvbox_dark";
        vim_keys = true;
        update_ms = 2000;
        show_cpu_freq = true;
        show_gpu = true;
        mem_graphs = true;
        proc_sorting = "cpu direct";
        proc_filter = false;
        tree_view = false;
        proc_per_core = true;
        proc_mem_bytes = true;
        cpu_graph_upper = "total";
        cpu_graph_lower = "user";
        cpu_invert_lower = true;
      };
    };

    services.activitywatch = {
      enable = true;
      package = pkgs.aw-server-rust;

      watchers = {
        awatcher = {
          package = pkgs.awatcher;
          settings = {
            idle-timeout-seconds = 60;
            poll-time-idle-seconds = 1;
            poll-time-window-seconds = 1;
          };
        };
      };
    };

    # ASBL mitigation and ActivityWatch systemd configuration
    systemd.user = {
      services = {
        asbl-no-moar = {
          Unit = {
            Description = "Wayland gamma poke to mitigate ASBL";
            After = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${asbl-fooler}/bin/asbl-no-moar";
            Restart = "no";
          };
          Install = {
            WantedBy = [ "default.target" ];
          };
        };

        activitywatch-watcher-awatcher =
          let
            target = "hyprland-session.target";
          in
          {
            Unit = {
              After = [ target ];
              Requisite = [ target ];
              PartOf = [ target ];
            };
            Install = {
              WantedBy = [ target ];
            };
          };
      };

      timers.asbl-no-moar = {
        Unit = {
          Description = "Timer for asbl-no-moar service";
        };
        Timer = {
          OnBootSec = "2min";
          OnUnitActiveSec = "150s";
          AccuracySec = "1s";
          Persistent = true;
        };
        Install = {
          WantedBy = [ "timers.target" ];
        };
      };
    };
  };
}
