# Waybar status bar configuration
{ pkgs, lib, inputs, ... }:
let
  script = rel: "${inputs.self}/scripts/${rel}";
  waybarAudioSignal = 12;
  audioOutputStatus = pkgs.writeShellApplication {
    name = "audio-output-status";
    runtimeInputs = with pkgs; [ coreutils gawk jq pipewire ];
    text = builtins.readFile (script "audio-output-status");
  };
  audioOutputToggle = pkgs.writeShellApplication {
    name = "toggle-audio-output";
    runtimeInputs = with pkgs; [ coreutils gawk jq pipewire procps ];
    text = builtins.readFile (script "toggle-audio-output");
  };
in
{
  home.packages = [ audioOutputToggle audioOutputStatus ];

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
}
