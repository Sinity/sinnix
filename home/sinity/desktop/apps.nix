{ pkgs, lib, ... }:
let
  waybarAudioSignal = 12;
  audioOutputStatus = pkgs.writeShellApplication {
    name = "audio-output-status";
    runtimeInputs = with pkgs; [
      coreutils
      gawk
      jq
      pipewire
    ];
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      if ! command -v wpctl >/dev/null 2>&1; then
        jq -n --arg text "󰓃" --arg tooltip "wpctl unavailable" --arg class "unavailable" '{text:$text, tooltip:$tooltip, class:$class}'
        exit 0
      fi

      inspect=$(wpctl inspect @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)
      if [[ -z "$inspect" ]]; then
        jq -n --arg text "󰓃" --arg tooltip "No default audio sink" --arg class "missing" '{text:$text, tooltip:$tooltip, class:$class}'
        exit 0
      fi

      description=$(printf '%s\n' "$inspect" | awk -F ' = ' '/node.description/ {gsub(/"/, "", $2); print $2; exit}')
      nick=$(printf '%s\n' "$inspect" | awk -F ' = ' '/node.nick/ {gsub(/"/, "", $2); print $2; exit}')
      name=$(printf '%s\n' "$inspect" | awk -F ' = ' '/node.name/ {gsub(/"/, "", $2); print $2; exit}')
      device=$(printf '%s\n' "$inspect" | awk -F ' = ' '/device.description/ {gsub(/"/, "", $2); print $2; exit}')

      label="$description"
      if [[ -z "$label" ]]; then
        label="$nick"
      fi
      if [[ -z "$label" ]]; then
        label="$name"
      fi
      if [[ -z "$label" ]]; then
        label="Audio Sink"
      fi

      lowered=$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]')

      icon="󰓃"
      class="speaker"

      if [[ "$lowered" == *"headphone"* || "$lowered" == *"headset"* ]]; then
        icon="󰋋"
        class="headphones"
      elif [[ "$lowered" == *"bluetooth"* || "$lowered" == *"bt"* ]]; then
        icon="󰂯"
        class="bluetooth"
      elif [[ "$lowered" == *"hdmi"* || "$lowered" == *"digital"* || "$lowered" == *"display"* || "$lowered" == *"monitor"* ]]; then
        icon="󰡁"
        class="hdmi"
      elif [[ "$lowered" == *"usb"* || "$lowered" == *"dac"* || "$lowered" == *"ifi"* ]]; then
        icon="󰂰"
        class="usb"
      fi

      short_label="$label"
      max_chars=28
      limit=$((max_chars - 1))
      if (( ''${#short_label} > max_chars )); then
        short_label="$(printf '%s' "$short_label" | cut -c1-"$limit")..."
      fi

      tooltip="$label"
      if [[ -n "$device" && "$device" != "$label" ]]; then
        tooltip="$label"$'\n'"$device"
      fi

      text_output="$icon $short_label"
      jq -n --arg text "$text_output" --arg tooltip "$tooltip" --arg class "$class" '{text:$text, tooltip:$tooltip, class:$class}'
    '';
  };
  audioOutputToggle = pkgs.writeShellApplication {
    name = "toggle-audio-output";
    runtimeInputs = with pkgs; [
      coreutils
      gawk
      jq
      pipewire
      procps
    ];
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      default_signal="${toString waybarAudioSignal}"
      signal="''${WAYBAR_AUDIO_OUTPUT_SIGNAL:-$default_signal}"

      inspect=$(wpctl inspect @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)
      if [[ -z "$inspect" ]]; then
        exit 1
      fi

      current_line=$(printf '%s\n' "$inspect" | head -n1)
      current_id=$(printf '%s\n' "$current_line" | awk '{print $2}' | tr -d ',')

      dump=$(pw-dump)

      mapfile -t sinks < <(printf '%s\n' "$dump" | jq -r '.[] | select(.type == "PipeWire:Interface:Node") | select(.info.props["media.class"] == "Audio/Sink") | .id' | sort -n | uniq)

      sinks_count=''${#sinks[@]}
      if (( sinks_count == 0 )); then
        exit 1
      fi

      next="''${sinks[0]}"
      for idx in "''${!sinks[@]}"; do
        if [[ "''${sinks[$idx]}" == "$current_id" ]]; then
          next="''${sinks[$(((idx + 1) % sinks_count))]}"
          break
        fi
      done

      if [[ "$next" == "$current_id" ]]; then
        exit 0
      fi

      wpctl set-default "$next"

      dump_after=$(pw-dump)
      mapfile -t streams < <(printf '%s\n' "$dump_after" | jq -r '.[] | select(.type == "PipeWire:Interface:Node") | select(.info.props["media.class"] == "Stream/Output/Audio") | .id')
      for stream in "''${streams[@]}"; do
        wpctl set-target "$stream" "$next" || true
      done

      pkill -RTMIN+"$signal" waybar 2>/dev/null || true
    '';
  };
in
{
  home.packages =
    (with pkgs; [
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
      wl-clip-persist
      wl-clipboard
      clipse
      fnott
      libnotify
    ])
    ++ [
      audioOutputToggle
      audioOutputStatus
    ];

  services.clipse = {
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

  services.fnott = {
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
      low.default-timeout = 5;
      normal.default-timeout = 10;
      critical.default-timeout = 0;
    };
  };

  programs.tofi = {
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
      fuzzy-match = true;
      late-keyboard-init = false;
      multi-instance = false;
      terminal = "kitty";
    };
  };

  programs.waybar = {
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
      #custom-audio-output { color: #83a598; }
      #custom-audio-output.speaker { color: #83a598; }
      #custom-audio-output.headphones { color: #d3869b; }
      #custom-audio-output.bluetooth { color: #8ec07c; }
      #custom-audio-output.hdmi { color: #fe8019; }
      #custom-audio-output.usb { color: #b8bb26; }
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
        "custom/audio-output"
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
      "custom/audio-output" = {
        format = "{}";
        return-type = "json";
        interval = 2;
        exec = "${audioOutputStatus}/bin/audio-output-status";
        signal = waybarAudioSignal;
        env = {
          WAYBAR_AUDIO_OUTPUT_SIGNAL = toString waybarAudioSignal;
        };
        on-click = "${audioOutputToggle}/bin/toggle-audio-output";
        on-click-right = "pwvucontrol";
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
            echo "<span font_family='SauceCodePro Nerd Font Mono'>󱅫</span>"
          else
            echo "<span font_family='SauceCodePro Nerd Font Mono'>󰂚</span>"
          fi
        ''}";
        interval = 1;
        on-click = "fnottctl dismiss";
        on-click-right = "fnottctl actions";
      };
    };
  };

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
        "application/pdf" = [ "google-chrome.desktop" ];
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
        "application/pdf" = [ "google-chrome.desktop" ];
        "text/html" = [ "google-chrome.desktop" ];
        "x-scheme-handler/http" = [ "google-chrome.desktop" ];
        "x-scheme-handler/https" = [ "google-chrome.desktop" ];
        "x-scheme-handler/about" = [ "google-chrome.desktop" ];
        "x-scheme-handler/unknown" = [ "google-chrome.desktop" ];
      };
    };
  };
}
