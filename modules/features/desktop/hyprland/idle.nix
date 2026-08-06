# Hyprland idle / DPMS management.
#
# The lock screen UI is provided by Noctalia (see noctalia.nix). This keeps
# hypridle only for display power management — blank the OLED on idle, restore
# on resume — and points the session lock action at Noctalia.
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
          timeout = 300;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };
}
