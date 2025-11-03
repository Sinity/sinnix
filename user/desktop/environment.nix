{
  config,
  ...
}:
let
  homeDir = config.home.homeDirectory;
in
{
  home.sessionVariables = {
    BROWSER = "qutebrowser";
    TERM = "kitty";
    TERMINAL = "kitty";

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
    KITTY_LISTEN_ON = "unix:" + "\${XDG_RUNTIME_DIR}/kitty-" + "\${USER}";

    LIBVA_DRIVER_NAME = "nvidia";
    GBM_BACKEND = "nvidia-drm";
    __GLX_VENDOR_LIBRARY_NAME = "nvidia";
    WLR_NO_HARDWARE_CURSORS = "1";
    __GL_GSYNC_ALLOWED = "1";
    __GL_VRR_ALLOWED = "1";

    _JAVA_AWT_WM_NONEREPARENTING = "1";
    DIRENV_LOG_FORMAT = "";
    NIXPKGS_ALLOW_UNFREE = "1";
    WINEDLLOVERRIDES = "winemenubuilder.exe=d";

    SESSION_HISTORY_FILE = "${homeDir}/.zsh_history";
    SESSION_CODEX_LOG = "${homeDir}/.codex/log/codex-tui.log";
    SESSION_CODEX_LOG_DIR = "${homeDir}/.codex/sessions";
  };
}
