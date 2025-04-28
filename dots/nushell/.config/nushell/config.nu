# Nushell Main Config (config.nu)
# Managed by dotfiles / home-manager

# --- Aliases ---

# Basic utilities
alias c = clear
alias cat = bat
alias py = python
alias icat = kitten icat

# Enhanced ls (eza)
alias ls = ls -a
alias ll = ls -l
alias tree = eza --icons --tree --group-directories-first

# NixOS commands
alias nix-switch = nh os switch
alias nix-update = nh os switch --update
alias nix-clean = nh clean all --keep 5
alias nix-search = nh search
alias nix-test = nh os test

# Other explicit utilities
alias pingg = ^ping 8.8.8.8
alias wtf = ^dmesg
alias ytd = yt-dlp

# --- Custom Functions ---

# --- Startup Tasks ---

# Prevent Ctrl+S terminal freezing (safe wrapped call)
try {
  ^stty -ixon
} catch {
  print $"[Warn] stty -ixon failed: ($in)"
}

# Atuin integration
use ~/.config/nushell/atuin.nu

# Starship integration (do similar if not already done)
use ~/.config/nushell/starship.nu

# zoxide integration
source ~/.config/nushell/zoxide.nu

# Make sure directory exists
mkdir ~/.asciinema_recordings | ignore

# record terminal sessions w/ asciinema
if ($env.ASCIINEMA_REC? | is-empty) {
  mkdir ~/realm/asciinema_recordings | ignore
  let timestamp = (date now | format date '%Y-%m-%d_%H-%M-%S')
  let file = $"($nu.home-path)/realm/asciinema_recordings/($timestamp).cast"
  exec asciinema rec -c nu $file | ignore
}

