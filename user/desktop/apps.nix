{ pkgs, lib, dotsPath, config, ... }:
let
  kvantumPkg =
    if lib.hasAttrByPath [ "qt6Packages" "qtstyleplugin-kvantum" ] pkgs then
      pkgs.qt6Packages.qtstyleplugin-kvantum
    else if lib.hasAttrByPath [ "libsForQt5" "kvantum" ] pkgs then
      pkgs.libsForQt5.kvantum
    else
      null;
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

      if [[ "$lowered" == *"wh-1000xm5"* || "$lowered" == *"galaxy buds2 pro"* ]]; then
        icon="󰋋"
        class="headphones"
      elif [[ "$lowered" == *"headphone"* || "$lowered" == *"headset"* ]]; then
        icon="󰋋"
        class="headphones"
      elif [[ "$lowered" == *"bluetooth"* || "$lowered" == *"bt"* ]]; then
        icon="󰂯"
        class="bluetooth"
      elif [[ "$lowered" == *"monitor"* || "$lowered" == *"display"* ]]; then
        icon="󰹑"
        class="monitor"
      elif [[ "$lowered" == *"hdmi"* || "$lowered" == *"digital"* ]]; then
        icon="󰡁"
        class="hdmi"
      elif [[ "$lowered" == *"usb"* || "$lowered" == *"dac"* || "$lowered" == *"ifi"* || "$lowered" == *"fiio"* || "$lowered" == *"e10k"* || "$lowered" == *"ultima 40"* ]]; then
        icon="󰓃"
        class="speaker"
      fi

      tooltip="$label"
      if [[ -n "$device" && "$device" != "$label" ]]; then
        tooltip="$label"$'\n'"$device"
      fi

      text_output="$icon"
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
      nautilus
      obsidian
      taskwarrior3
      timewarrior
      bleachbit
      transmission_3-gtk
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
      wlr-randr
    ])
    ++ [
      audioOutputToggle
      audioOutputStatus
    ];

  programs.mullvad-vpn = {
    enable = true;
    settings = {
      preferredLocale = "system";
      autoConnect = false;
      enableSystemNotifications = true;
      monochromaticIcon = false;
      startMinimized = true;
      unpinnedWindow = true;
      browsedForSplitTunnelingApplications = [ ];
      changelogDisplayedForVersion = "2025.2";
      animateMap = true;
    };
  };

  qt = {
    enable = true;
    platformTheme = {
      name = "qtct";
    };
    style =
      {
        name = "kvantum";
      }
      // lib.optionalAttrs (kvantumPkg != null) {
        package = kvantumPkg;
      };
  };

  home.activation.cleanupKvantum =
    lib.hm.dag.entryBefore [ "linkGeneration" ] ''
      rm -rf "$HOME/.config/Kvantum"
    '';


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

  services.fnott =
    let
      stylixColors = config.lib.stylix.colors;
      toRgba = alpha: color: let hex = lib.removePrefix "#" color; in "${hex}${alpha}";
      bg = toRgba "f0" stylixColors.base00;
      border = toRgba "ff" stylixColors.base03;
      text = toRgba "ff" stylixColors.base06;
      subtle = toRgba "ff" stylixColors.base04;
      accent = toRgba "ff" stylixColors.base0D;
      criticalBg = toRgba "f0" stylixColors.base08;
      fontMono = "SauceCodePro Nerd Font Mono:size=16";
    in
    {
      enable = true;
      settings = {
        main = {
          notification-margin = 8;
          anchor = "top-right";
          layer = "overlay";
          max-width = 400;
          max-height = 240;
          min-width = 320;
          border-size = 2;
          border-radius = 10;
          padding-horizontal = 14;
          padding-vertical = 10;
          progress-bar-height = 4;
          dpi-aware = true;
          background = lib.mkForce bg;
          border-color = lib.mkForce border;
          title-font = lib.mkForce fontMono;
          title-color = lib.mkForce text;
          summary-font = lib.mkForce fontMono;
          summary-color = lib.mkForce text;
          body-font = lib.mkForce fontMono;
          body-color = lib.mkForce subtle;
          progress-color = lib.mkForce accent;
        };
        low = {
          background = lib.mkForce bg;
          title-color = lib.mkForce subtle;
          summary-color = lib.mkForce subtle;
          body-color = lib.mkForce subtle;
          default-timeout = 5;
        };
        normal = {
          background = lib.mkForce bg;
          title-color = lib.mkForce text;
          summary-color = lib.mkForce text;
          body-color = lib.mkForce subtle;
          default-timeout = 10;
        };
        critical = {
          background = lib.mkForce criticalBg;
          border-color = lib.mkForce accent;
          title-color = lib.mkForce text;
          summary-color = lib.mkForce text;
          body-color = text;
          default-timeout = 0;
        };
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
      #custom-audio-output { color: #83a598; }
      #custom-audio-output.speaker { color: #83a598; }
      #custom-audio-output.headphones { color: #d3869b; }
      #custom-audio-output.bluetooth { color: #8ec07c; }
      #custom-audio-output.hdmi { color: #fe8019; }
      #custom-audio-output.monitor { color: #fe8019; }
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
      };
      "hyprland/workspaces" = {
        on-scroll-up = "hyprctl dispatch workspace e+1";
        on-scroll-down = "hyprctl dispatch workspace e-1";
        format = "{name}";
        sort-by-number = true;
        persistent-workspaces =
          builtins.listToAttrs (map (n: {
            name = toString n;
            value = [ ];
          }) (lib.range 1 10));
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
        format = "{text}";
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
    configFile = {
      "yazi/opener.toml" = {
        source = dotsPath + "/yazi/opener.toml";
        force = true;
      };
      "yazi/keymap.toml" = {
        source = dotsPath + "/yazi/keymap.toml";
        force = true;
      };
      "audacity/audacity.cfg".source = dotsPath + "/audacity/audacity.cfg";
      "qt5ct/qt5ct.conf".source = dotsPath + "/qt5ct/qt5ct.conf";
      "qt6ct/qt6ct.conf".source = dotsPath + "/qt6ct/qt6ct.conf";
      "Kvantum" = {
        source = dotsPath + "/Kvantum";
        recursive = true;
      };
      "transmission/settings.json".source = dotsPath + "/transmission/settings.json";
      "autostart/mullvad-vpn.desktop".text = ''
        [Desktop Entry]
        Type=Application
        Name=Mullvad VPN (disabled)
        Hidden=true
      '';
      "mimeapps.list".force = true;
    };
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
