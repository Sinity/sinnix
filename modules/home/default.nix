{
  inputs,
  username,
  host,
  ...
}: {
  imports = [
    ./activity_watch.nix # self-inflicted telemetry
    ./discord/discord.nix # discord with catppuccin theme
    ./gaming.nix # packages related to gaming
    ./gtk.nix # gtk theme
    ./hydrus.nix # hydrus with custom setup
    ./hyprland # window manager
    ./starship.nix # prompt
    ./swaync/swaync.nix # notification deamon
    ./packages.nix # other packages
    ./scripts/scripts.nix # personal scripts
    ./vscodium.nix # vscode fork
    ./waybar # status bar
    ./xdg-mimes.nix # xdg config
    ./zsh.nix # shell
  ];
}
