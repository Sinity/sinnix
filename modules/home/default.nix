{
  inputs,
  username,
  host,
  ...
}: {
  imports = [
    ./activity_watch.nix # self-inflicted telemetry
    ./discord/discord.nix # discord with catppuccin theme
    ./hydrus.nix # hydrus with custom setup
    ./enhanced-imv.nix # image viewer, with support of common formats
    ./hyprland # window manager
    ./starship.nix # prompt
    ./swaync/swaync.nix # notification deamon
    ./packages.nix # other packages
    ./scripts/scripts.nix # personal scripts
    ./waybar # status bar
    ./xdg-mimes.nix # xdg config (possibly unnecessary, so I'll comment it out and see)
    ./zsh.nix # shell
  ];
}
