{ ... }:
{
  imports = [
    ./cli/default.nix
    ./desktop/activitywatch.nix
    ./desktop/audio.nix
    ./desktop/base.nix
    ./desktop/browser.nix
    ./desktop/common-apps.nix
    ./desktop/crypto.nix
    ./desktop/gaming.nix
    ./desktop/hyprland/default.nix
    ./desktop/media.nix
    ./desktop/mime.nix
    ./desktop/reboot-notifier.nix
    ./desktop/storage.nix
    ./desktop/terminal.nix
    ./desktop/theming.nix
    ./desktop/ui.nix
    ./desktop/waybar.nix
    ./dev/default.nix
  ];
}
