{
  inputs,
  username,
  host,
  ...
}: {
  imports = [
    # Consolidated Modules
    ./shell.nix # Contains bat, fzf, zsh, starship, atuin, zoxide, broot
    ./kitty.nix
    ./desktop.nix # Contains gtk, waybar, swaync

    # Remaining Separate Modules
    ./git.nix
    ./ssh.nix

    # Existing Modules
    ./activity_watch.nix # self-inflicted telemetry
    ./discord/discord.nix # discord with catppuccin theme
    ./hydrus.nix # hydrus with custom setup
    ./enhanced-imv.nix # image viewer, with support of common formats
    ./hyprland # window manager
    ./packages.nix # other packages
    ./scripts/scripts.nix # personal scripts
    ./xdg-mimes.nix # xdg config (possibly unnecessary, so I'll comment it out and see)
    ./asbl-no-moar.nix # Wayland gamma poke for ASBL mitigation
  ];
}
