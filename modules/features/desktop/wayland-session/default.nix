{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.wayland-session;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.desktop.wayland-session = {
    enable = lib.mkEnableOption "Wayland Session Environment & Tools";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { config, pkgs, ... }: 
      let
        homeDir = config.home.homeDirectory;
      in
      {
        home.packages = with pkgs; [
          swaybg
          hyprpicker
          wl-gammactl
        ];

        home.sessionVariables = {
          BROWSER = "google-chrome-stable";
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

          _JAVA_AWT_WM_NONEREPARENTING = "1";
          DIRENV_LOG_FORMAT = "";
          NIXPKGS_ALLOW_UNFREE = "1";
          WINEDLLOVERRIDES = "winemenubuilder.exe=d";

          SESSION_HISTORY_FILE = "${homeDir}/.zsh_history";
        };
      };
  };
}
