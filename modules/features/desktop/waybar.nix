{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "waybar"
  ];
  description = "Waybar status bar";
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      ...
    }:
    let
      sinnix = config.sinnix;
      scriptPath = rel: "${sinnix.paths.projectRoot}/scripts/${rel}";
      waybarAudioSignal = 12;
      audioBin = scriptPath "audio";
    in
    {
      home-manager.users.${user} =
        { pkgs, lib, ... }:
        {
          programs.waybar = {
            enable = true;
            systemd.enable = true;
            package = pkgs.waybar;
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
              #custom-pressure,
              #custom-agent,
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
              #custom-pressure { color: #b8bb26; }
              #custom-pressure.ok { color: #b8bb26; }
              #custom-pressure.warn { color: #fabd2f; }
              #custom-pressure.fail { color: #fb4934; }
              #custom-audio { color: #83a598; }
              #custom-audio.muted { color: #665c54; }
              #custom-audio.headphones { color: #d3869b; }
              #custom-audio.bluetooth { color: #8ec07c; }
              #custom-audio.hdmi,
              #custom-audio.monitor { color: #fe8019; }
              #custom-audio.usb { color: #b8bb26; }

              #custom-agent { color: #83a598; }
              #custom-agent.idle { color: #665c54; }
              #custom-agent.live { color: #83a598; }
              #custom-agent.pending {
                color: #fabd2f;
                border-color: rgba(250, 189, 47, 0.6);
                background-color: rgba(250, 189, 47, 0.12);
              }
              #custom-agent.missing { color: #fb4934; }
              #custom-agent.unhealthy {
                color: #fb4934;
                border-color: rgba(251, 73, 52, 0.7);
                background-color: rgba(251, 73, 52, 0.18);
              }

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
                "custom/pressure"
                "custom/agent"
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
                exec = "${audioBin} status";
                on-click = "${audioBin} toggle";
                on-click-right = "${audioBin} mute";
                on-scroll-up = "${audioBin} volume-up";
                on-scroll-down = "${audioBin} volume-down";
                on-click-middle = "pwvucontrol";
              };
              "custom/launcher" = {
                format = "<span font_family='SauceCodePro Nerd Font Mono'>󰀻</span>";
                on-click = "tofi-drun --drun-launch=true";
                tooltip = "false";
              };
              "custom/pressure" = {
                tooltip = true;
                format = "{}";
                return-type = "json";
                interval = 5;
                exec = "${pkgs.writeShellScript "waybar-pressure" ''
                  read_psi() {
                    ${pkgs.gawk}/bin/awk -v metric="$1" '
                      $1 == "some" {
                        for (i = 2; i <= NF; i++) {
                          split($i, kv, "=")
                          if (kv[1] == metric) {
                            print kv[2]
                            exit
                          }
                        }
                      }
                    ' "$2"
                  }

                  io10="$(read_psi avg10 /proc/pressure/io)"
                  io60="$(read_psi avg60 /proc/pressure/io)"
                  io300="$(read_psi avg300 /proc/pressure/io)"
                  mem10="$(read_psi avg10 /proc/pressure/memory)"
                  mem60="$(read_psi avg60 /proc/pressure/memory)"
                  mem300="$(read_psi avg300 /proc/pressure/memory)"
                  cpu10="$(read_psi avg10 /proc/pressure/cpu)"
                  cpu60="$(read_psi avg60 /proc/pressure/cpu)"
                  cpu300="$(read_psi avg300 /proc/pressure/cpu)"

                  state="$(${pkgs.gawk}/bin/awk -v io="$io10" -v mem="$mem10" 'BEGIN {
                    worst = io > mem ? io : mem
                    if (worst >= 20) print "fail"
                    else if (worst >= 5) print "warn"
                    else print "ok"
                  }')"
                  text="$(${pkgs.gawk}/bin/awk -v io="$io10" 'BEGIN {
                    if (io >= 1) printf "io %.0f", io
                    else printf "psi"
                  }')"
                  printf '{"text":"%s","class":"%s","tooltip":"io avg10=%s avg60=%s avg300=%s\\nmem avg10=%s avg60=%s avg300=%s\\ncpu avg10=%s avg60=%s avg300=%s"}\n' \
                    "$text" "$state" "$io10" "$io60" "$io300" "$mem10" "$mem60" "$mem300" "$cpu10" "$cpu60" "$cpu300"
                ''}";
                on-click = "kitty -e sinnix-observe";
              };
              "custom/agent" = {
                tooltip = true;
                format = "{}";
                return-type = "json";
                interval = 5;
                exec = "${pkgs.writeShellScript "waybar-agent" ''
                  set -euo pipefail
                  if [ -x /home/sinity/.local/bin/agent-state ]; then
                    /home/sinity/.local/bin/agent-state --waybar
                  else
                    echo '{"text":"agent?","alt":"missing","class":"missing","tooltip":"agent-state not on PATH"}'
                  fi
                ''}";
                on-click = "/home/sinity/.local/bin/agent-surface";
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
                # Poll every 10 seconds instead of 1 to reduce journal spam
                # (fnott logs 2 messages per poll = 17,280/day at 1s)
                interval = 10;
                on-click = "fnottctl dismiss";
                on-click-right = "fnottctl actions";
              };
            };
          };
        };
    };
} args
