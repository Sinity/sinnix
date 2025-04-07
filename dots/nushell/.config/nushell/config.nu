# Nushell Main Config (config.nu)
# Managed by dotfiles / home-manager

# --- Aliases ---

# Basic utilities
alias c = clear
alias cat = bat
alias py = python
alias icat = kitten icat
alias open = xdg-open

# Enhanced ls (eza)
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
alias man = ^BAT_THEME='default' batman

# --- Custom Functions ---

# Function: Update terminal title dynamically
def update_terminal_title [cmd: string = ""] {
  let dir = ($env.PWD | str replace $env.HOME "~")
  let time = (date now | format date "%Y-%m-%d %H:%M:%S")
  let title = if $cmd == "" {
    $"($dir); ($time)"
  } else {
    $"($dir); ($time) ($cmd)"
  }
  # ESC (\u{1b}) and BEL (\u{07}) for OSC sequence
  $"\u{1b}]2;($title)\u{07}" | print -n
}

# --- Nushell Hooks ---

# Safely initialize hooks
$env.hooks = ($env.hooks? | default {
  pre_prompt: [],
  pre_execution: [],
  env_change: []
})

# Append custom hook functions
$env.hooks.pre_prompt = ($env.hooks.pre_prompt | append {|| update_terminal_title ""})
$env.hooks.pre_execution = ($env.hooks.pre_execution | append {|cmd| update_terminal_title $cmd})

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

# --- Integrations Notice ---

# zoxide and atuin integrations are managed via home-manager.
# No manual configuration needed here.

