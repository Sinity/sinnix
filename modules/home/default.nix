{
  inputs,
  username,
  host,
  ...
}: {
  imports = [
    ./activity_watch.nix # self-inflicted telemetry
    ./bat.nix # better cat command
    ./btop.nix # resouces monitor
    ./discord/discord.nix # discord with catppuccin theme
    ./fzf.nix # fuzzy finder
    ./gaming.nix # packages related to gaming
    ./gtk.nix # gtk theme
    ./hydrus.nix # hydrus with custom setup
    ./hyprland # window manager
    ./kitty.nix # terminal
    ./ranger.nix # TUI file manager
    ./swaync/swaync.nix # notification deamon
    ./packages.nix # other packages
    ./rofi.nix # launcher
    ./scripts/scripts.nix # personal scripts
    ./starship.nix # shell prompt
    ./vscodium.nix # vscode fork
    ./waybar # status bar
    ./xdg-mimes.nix # xdg config
    ./mpv.nix
  ];
}
