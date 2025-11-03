# Waybar status bar configuration
{
  pkgs,
  lib,
  inputs,
  ...
}:
let
  script = rel: "${inputs.self}/scripts/${rel}";
  waybarAudioSignal = 12;
  audioOutputStatus = pkgs.writeShellApplication {
    name = "audio-output-status";
    runtimeInputs = with pkgs; [
      coreutils
      gawk
      jq
      pipewire
    ];
    text = builtins.readFile (script "audio-output-status");
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
    text = builtins.readFile (script "toggle-audio-output");
  };
in
{
  home.packages = [
    audioOutputToggle
    audioOutputStatus
  ];

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
        font-size: 18px;
      }

      window#waybar {
        background-color: rgba(18, 19, 24, 0.9);
        border: 1px solid rgba(160, 175, 205, 0.22);
        border-radius: 12px;
        margin: 10px 22px;
        padding: 10px 16px;
      }

      #waybar .modules-right > widget > * {
        margin: 0 10px;
      }

      #waybar .modules-right > widget:last-child > * {
        margin-right: 0;
      }

      #workspaces button {
        padding: 4px 10px;
        margin: 0 4px;
        border-radius: 8px;
        border: 1px solid transparent;
        color: rgba(232, 230, 223, 0.7);
        background-color: transparent;
      }

      #workspaces button.focused {
        color: #8ec07c;
        border-color: rgba(142, 192, 124, 0.5);
        background-color: rgba(142, 192, 124, 0.18);
      }

      #workspaces button.visible:not(.focused) {
        color: #fbf1c7;
        background-color: rgba(142, 192, 124, 0.12);
      }

      #workspaces button.urgent {
        color: #fb4934;
        border-color: rgba(251, 73, 52, 0.6);
        background-color: rgba(251, 73, 52, 0.18);
      }

      #workspaces button:hover {
        color: #fbf1c7;
        border-color: rgba(142, 192, 124, 0.4);
      }

      #custom-launcher,
      #cpu,
      #memory,
      #disk,
      #custom-audio,
      #custom-notification,
      #tray {
        background-color: rgba(40, 42, 54, 0.75);
        border-radius: 10px;
        border: 1px solid rgba(120, 132, 162, 0.35);
        padding: 4px 10px;
      }

      #cpu { color: #fb4934; }
      #memory { color: #fabd2f; }
      #disk { color: #b8bb26; }
      #custom-audio { color: #83a598; }
      #custom-audio.muted { color: #665c54; }
      #custom-audio.headphones { color: #d3869b; }
      #custom-audio.bluetooth { color: #8ec07c; }
      #custom-audio.hdmi,
      #custom-audio.monitor { color: #fe8019; }
      #custom-audio.usb { color: #b8bb26; }

      #tray button,
      #tray .item {
        border-radius: 6px;
        padding: 2px 4px;
      }

      #tray button:hover,
      #tray .item:hover {
        background-color: rgba(55, 57, 68, 0.9);
      }
    '';
    settings.mainBar = {
      position = "bottom";
      layer = "top";
      height = 42;
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
        "custom/audio"
        "custom/notification"
      ];
      clock = {
        format = "<span font_family='SauceCodePro Nerd Font Mono'>󱑎</span> {:%a %d · %H:%M}";
        tooltip = "true";
      };
      "hyprland/workspaces" = {
        on-scroll-up = "hyprctl dispatch workspace e+1";
        on-scroll-down = "hyprctl dispatch workspace e-1";
        format = "{name}";
        sort-by-number = true;
        persistent-workspaces = builtins.listToAttrs (
          map (n: {
            name = toString n;
            value = [ ];
          }) (lib.range 1 10)
        );
      };
      cpu = {
        format = "<span font_family='SauceCodePro Nerd Font Mono'>󰍛</span> {usage}%";
        format-alt = "<span font_family='SauceCodePro Nerd Font Mono'>󰍛</span> {avg_frequency}GHz";
        interval = 2;
        on-click = "kitty -e btop";
      };
      memory = {
        format = "<span font_family='SauceCodePro Nerd Font Mono'>󰟜</span> {percentage}%";
        format-alt = "<span font_family='SauceCodePro Nerd Font Mono'>󰟜</span> {used}GB";
        interval = 2;
        on-click = "kitty -e btop";
      };
      disk = {
        format = "<span font_family='SauceCodePro Nerd Font Mono'>󰋊</span> {percentage_used}%";
        interval = 60;
        on-click = "kitty -e ncdu ~";
      };
      tray = {
        icon-size = 20;
        spacing = 8;
      };
      "custom/audio" = {
        format = "{text}";
        return-type = "json";
        interval = 2;
        signal = waybarAudioSignal;
        exec = "${audioOutputStatus}/bin/audio-output-status";
        env = {
          WAYBAR_AUDIO_OUTPUT_SIGNAL = toString waybarAudioSignal;
        };
        on-click = "${audioOutputToggle}/bin/toggle-audio-output";
        on-click-right = "pamixer -t";
        on-scroll-up = "pamixer -i 2";
        on-scroll-down = "pamixer -d 2";
        on-click-middle = "pwvucontrol";
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
}
