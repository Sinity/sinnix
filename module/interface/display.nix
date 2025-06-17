# Display and Color Management Configuration
# Wallpaper, color temperature, gamma control, and visual effects

{ pkgs, ... }:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          # Color and appearance
          swaybg # Wallpaper utility
          hyprpicker # Color picker
          wl-gammactl # Adjust gamma
          wlsunset # Night light/blue light filter
          redshift # Adjust color temperature (X11/Wayland)
        ];
      };
    };
  };
}
