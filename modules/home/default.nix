{inputs, username, host, ...}: {
  imports = [
    ./activity_watch.nix              # self-inflicted telemetry
    ./bat.nix                         # better cat command
    ./btop.nix                        # resouces monitor 
    ./discord/discord.nix             # discord with catppuccin theme
    ./fzf.nix                         # fuzzy finder
    ./gaming.nix                      # packages related to gaming
    ./git.nix                         # version control
    ./gnome.nix                       # gnome apps
    ./gtk.nix                         # gtk theme
    ./hyprland                        # window manager
    ./kitty.nix                       # terminal
    ./ranger.nix                      # TUI file manager
    ./swaync/swaync.nix               # notification deamon
    ./nvim.nix                        # neovim editor
    ./packages.nix                    # other packages
    ./rofi.nix                        # launcher
    ./scripts/scripts.nix             # personal scripts
    ./starship.nix                    # shell prompt
    ./vscodium.nix                    # vscode fork
    ./waybar                          # status bar
    ./xdg-mimes.nix                   # xdg config
    ./zsh.nix                         # shell
    ./mpv.nix
  ];
}
