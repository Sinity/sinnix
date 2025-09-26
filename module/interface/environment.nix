# Desktop Environment Variables
# Wayland, Hyprland, and application-specific environment configuration

_: {
  config = {
    home-manager.users.sinity = {
      home = {
        # Environment variables for proper Wayland/Hyprland operation
        sessionVariables = {
          BROWSER = "google-chrome-beta";
          TERM = "kitty";
          TERMINAL = "kitty";

          # Wayland/Hyprland specific
          XDG_SESSION_TYPE = "wayland";
          XDG_CURRENT_DESKTOP = "Hyprland";
          XDG_SESSION_DESKTOP = "Hyprland";
          XDG_DESKTOP_PORTAL_DIR = "/run/current-system/sw/share/xdg-desktop-portal/portals";
          GDK_BACKEND = "wayland";
          SDL_VIDEODRIVER = "wayland";
          CLUTTER_BACKEND = "wayland";
          MOZ_ENABLE_WAYLAND = "1";
          ANKI_WAYLAND = "1";
          NIXOS_OZONE_WL = "1";
          ELECTRON_OZONE_PLATFORM_HINT = "wayland";
          OZONE_PLATFORM = "wayland";
          OZONE_PLATFORM_HINT = "wayland";

          # NVIDIA specific
          LIBVA_DRIVER_NAME = "nvidia";
          GBM_BACKEND = "nvidia-drm";
          __GLX_VENDOR_LIBRARY_NAME = "nvidia";
          WLR_NO_HARDWARE_CURSORS = "1";
          __GL_GSYNC_ALLOWED = "1";
          __GL_VRR_ALLOWED = "1";

          # Other environment settings
          _JAVA_AWT_WM_NONEREPARENTING = "1";
          DIRENV_LOG_FORMAT = "";
          NIXPKGS_ALLOW_UNFREE = "1";
          WINEDLLOVERRIDES = "winemenubuilder.exe=d";
        };
      };
    };
  };
}
