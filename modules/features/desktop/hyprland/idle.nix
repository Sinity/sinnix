# Hyprland idle / DPMS management.
#
# The lock screen UI is provided by Noctalia (see noctalia.nix). This keeps
# hypridle owns the ordered OLED power and lock stages. Media and game
# inhibitors remain in the Hyprland rules module.
#
_: {
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        after_sleep_cmd = "hyprctl dispatch dpms on";
        ignore_dbus_inhibit = false;
        lock_cmd = "noctalia msg session lock";
      };

      listener = [
        {
          timeout = 1800;
          on-timeout = "sinnix-ops-afk-start";
          on-resume = "sinnix-ops-afk-resume";
        }
        {
          timeout = 420;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
        {
          timeout = 1500;
          on-timeout = "noctalia msg session lock";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };
}
