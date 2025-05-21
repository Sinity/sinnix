{ pkgs, ... }:
{
  #
  # Hyprland Wayland Compositor Configuration
  #

  imports = [
    ./config.nix # Hyprland specific configuration
    ./hyprlock.nix # Screen locking configuration
  ];

  # Required packages for Hyprland environment
  home.packages = with pkgs; [
    # Screenshot and screen recording utilities
    grim # Screenshot utility
    slurp # Region selection tool
    grimblast # Screenshot tool using grim and slurp
    wl-screenrec # Screen recording

    # Clipboard management
    wl-clip-persist # Keep clipboard content after application closes

    # Color and appearance
    swaybg # Wallpaper utility
    hyprpicker # Color picker
    wl-gammactl # Adjust gamma
    wlsunset # Night light/blue light filter

    # Dependencies and libraries
    glib # GLib library
    wayland # Wayland protocol library
    egl-wayland # EGL support for Wayland
    direnv # Directory environment manager
  ];

  # Ensure standard desktop autostart entries run
  systemd.user.targets.hyprland-session.Unit.Wants = [ "xdg-desktop-autostart.target" ];

  # Basic Hyprland configuration
  wayland.windowManager.hyprland = {
    enable = true;

    # Enable X11 compatibility
    xwayland = {
      enable = true;
    };

    # Use systemd for managing the Hyprland session
    systemd.enable = true;
  };

  # Environment variables for proper Wayland/Hyprland operation
  home.sessionVariables = {
    # Wayland-specific environment variables
    XDG_SESSION_TYPE = "wayland";
    XDG_CURRENT_DESKTOP = "Hyprland";
    XDG_SESSION_DESKTOP = "Hyprland";
    XDG_DESKTOP_PORTAL_DIR = "/run/current-system/sw/share/xdg-desktop-portal/portals";

    # Force applications to use Wayland
    GDK_BACKEND = "wayland";
    SDL_VIDEODRIVER = "wayland";
    CLUTTER_BACKEND = "wayland";
    MOZ_ENABLE_WAYLAND = "1";
    ANKI_WAYLAND = "1"; # Anki

    # Electron apps
    NIXOS_OZONE_WL = "1";
    ELECTRON_OZONE_PLATFORM_HINT = "wayland";
    OZONE_PLATFORM = "wayland";
    OZONE_PLATFORM_HINT = "wayland";

    # NVIDIA-specific settings
    LIBVA_DRIVER_NAME = "nvidia";
    GBM_BACKEND = "nvidia-drm";
    __GLX_VENDOR_LIBRARY_NAME = "nvidia";
    WLR_NO_HARDWARE_CURSORS = "1";

    # Graphics settings
    __GL_GSYNC_ALLOWED = "1";
    __GL_VRR_ALLOWED = "1";

    # Various application fixes
    _JAVA_AWT_WM_NONEREPARENTING = "1"; # Fix for Java applications
    SSH_AUTH_SOCK = "/run/user/1000/keyring/ssh";
    DIRENV_LOG_FORMAT = "";
    NIXPKGS_ALLOW_UNFREE = "1";
  };
}
