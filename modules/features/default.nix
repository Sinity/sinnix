{ ... }:
{
  imports = [
    ./cli/default.nix
    ./desktop/activitywatch.nix
    ./desktop/background-services.nix
    ./desktop/browser.nix
    ./desktop/clipse.nix
    ./desktop/common-apps.nix
    ./desktop/theming.nix
    ./desktop/mime.nix
    ./desktop/gaming.nix
    ./desktop/crypto.nix
    ./desktop/fnott.nix
    ./desktop/hyprland/default.nix
    ./desktop/kdeconnect.nix
    ./desktop/media.nix
    ./desktop/mullvad.nix
    ./desktop/quickshell.nix
    ./desktop/reboot-notifier.nix
    ./desktop/storage.nix
    ./desktop/terminal.nix
    ./desktop/tofi.nix
    ./desktop/waybar.nix
    ./desktop/wayland-session.nix
    ./dev/default.nix
  ];
}
