{inputs, username, host, ...}: {
  imports = [
    ./activity_watch.nix              # self-inflicted telemetry
    ./bat.nix                         # better cat command
    ./btop.nix                        # resouces monitor 
    ./cava.nix                        # audio visualizer
    ./discord/discord.nix                     # discord with catppuccin theme
    ./fastfetch.nix                         # fetch tool
    ./floorp/floorp.nix               # firefox based browser
    ./fzf.nix                         # fuzzy finder
    ./gaming.nix                      # packages related to gaming
    ./git.nix                         # version control
    ./gnome.nix                         # gnome apps
    ./gtk.nix                         # gtk theme
    ./hyprland                        # window manager
    ./kitty.nix                       # terminal
    ./ranger.nix                      # TUI file manager
    ./swaync/swaync.nix               # notification deamon
    ./nvim.nix                        # neovim editor
    ./packages.nix                    # other packages
    ./rofi.nix                        # launcher
    ./scripts/scripts.nix             # personal scripts
    ./spicetify.nix                   # spotify client
    ./starship.nix                    # shell prompt
    ./swaylock.nix                    # lock screen
    ./vscodium.nix                    # vscode fork
    ./waybar                          # status bar
    ./xdg-mimes.nix                   # xdg config
    ./zsh.nix                         # shell
    ./mpv.nix
  ];
}
