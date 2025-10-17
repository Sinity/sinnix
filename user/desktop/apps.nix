{ pkgs, lib, dotsPath, ... }:
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

  xdg.configFile."yazi/opener.toml".source = dotsPath + "/yazi/opener.toml";
  xdg.configFile."yazi/keymap.toml".source = dotsPath + "/yazi/keymap.toml";

  home.file.".config/yazi/opener.toml".force = true;
  home.file.".config/yazi/keymap.toml".force = true;
*** End Patch
