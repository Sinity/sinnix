{
  inputs,
  username,
  host,
  ...
}: {
  imports = [
    ./shell.nix
    ./desktop.nix
    ./kitty.nix
    ./git.nix
    ./ssh.nix

    ./activity_watch.nix # self-inflicted telemetry
    ./hydrus.nix # hydrus with custom setup
    ./hyprland # window manager
    ./packages.nix # other packages
    ./scripts/scripts.nix # personal scripts
    ./xdg-mimes.nix # xdg config (possibly unnecessary, so I'll comment it out and see)
    # ./enhanced-imv.nix # image viewer, with support of common formats
    # ./asbl-no-moar.nix # Wayland gamma poke for ASBL mitigation
  ];
}
