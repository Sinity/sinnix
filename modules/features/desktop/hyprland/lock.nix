# Hyprland screen locking and idle management
{ pkgs, inputs, ... }:
{
  xdg.configFile."hypr/hyprlock.conf".text = ''
    # BACKGROUND
    background {
      monitor =
      path = ${inputs.self + "/assets/wallpaper-sinnix.svg"}
      blur_passes = 1
      contrast = 0.8916
      brightness = 0.8172
      vibrancy = 0.1696
      vibrancy_darkness = 0.0
    }

    # GENERAL
    general {
      hide_cursor = true
      no_fade_in = false
      grace = 0
      disable_loading_bar = false
    }

    # Time
    label {
      monitor =
      text = cmd[update:1000] echo "$(date +"%k:%M")"
      font_size = 111
      position = 0, 270
      halign = center
      valign = center
    }

    # Day
    label {
      monitor =
      text = cmd[update:1000] echo "- $(date +"%A, %B %d") -"
      font_size = 20
      position = 0, 160
      halign = center
      valign = center
    }

    # USER-BOX
    shape {
      monitor =
      size = 350, 50
      rounding = 15
      border_size = 0
      rotate = 0

      position = 0, -230
      halign = center
      valign = center
    }

    # USER
    label {
      monitor =
      text =   $USER
      font_size = 16
      position = 0, -230
      halign = center
      valign = center
    }

    # INPUT FIELD
    input-field {
      monitor =
      size = 350, 50
      outline_thickness = 0
      rounding = 15
      dots_size = 0.25
      dots_spacing = 0.4
      dots_center = true
      fade_on_empty = false
      placeholder_text = <i>Enter Password</i>
      hide_input = false
      position = 0, -300
      halign = center
      valign = center
    }
  '';

  services.hypridle = {
    enable = true;
    settings = {
      general = {
        after_sleep_cmd = "hyprctl dispatch dpms on";
        ignore_dbus_inhibit = false;
        lock_cmd = "hyprlock";
      };

      listener = [
        {
          timeout = 300;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };

  home.packages = with pkgs; [
    hyprlock
  ];
}
