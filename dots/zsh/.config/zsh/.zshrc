# Disable auto update and magic functions
DISABLE_AUTO_UPDATE=true
DISABLE_MAGIC_FUNCTIONS=true
export "MICRO_TRUECOLOR=1"

# Oh-My-Zsh Configuration
export ZSH="$HOME/.oh-my-zsh"
plugins=(git python man)
source $ZSH/oh-my-zsh.sh

# use vi-like keybinds in shell
set -o vi

# Use fd (https://github.com/sharkdp/fd) for listing path candidates.
# - The first argument to the function ($1) is the base path to start traversal
# - See the source code (completion.{bash,zsh}) for the details.
_fzf_compgen_path() {
  fd --hidden --exclude .git . "$1"
}

# Use fd to generate the list for directory completion
_fzf_compgen_dir() {
  fd --type=d --hidden --exclude .git . "$1"
}

# Advanced customization of fzf options via _fzf_comprun function
# - The first argument to the function is the name of the command.
# - You should make sure to pass the rest of the arguments to fzf.
_fzf_comprun() {
  local command=$1
  shift

  case "$command" in
    cd)           fzf --preview 'eza --tree --color=always {} | head -200' "$@" ;;
    ssh)          fzf --preview 'dig {}'                   "$@" ;;
    *)            fzf --preview "$show_file_or_dir_preview" "$@" ;;
  esac
}

# Fix Ctrl+S in terminal
stty -ixon

# Terminal title useful for activity tracking
update_terminal_title() {
  LAST_CMD=$1
  TITLE="\033]2;$(pwd); $(date "+%Y-%m-%d %H:%M:%S") $LAST_CMD\007"
  echo -ne $TITLE
}
preexec() { update_terminal_title "$1" }
precmd() { update_terminal_title "" }

autoload -U add-zsh-hook
add-zsh-hook preexec preexec
add-zsh-hook precmd precmd
zmodload zsh/zpty

# fix url params
autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic
autoload -Uz url-quote-magic
zle -N self-insert url-quote-magic

# Environment variables
export EDITOR="nvim"
export VISUAL="nvim"
export PAGER="less"
export BROWSER="zen"
export TERM="kitty"
export TERMINAL="kitty"

export FLAKE="/mnt/ssd_storage/home/nixos-config"

export PYTHONDONTWRITEBYTECODE="1"
export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS="0"
export LD_LIBRARY_PATH="$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib"

# Add scripts to path
export PATH="$PATH:$HOME/scripts:$HOME/scripts/yeelight"

# Enable zoxide
eval "$(zoxide init zsh)"

# Utils
alias c="clear"
alias cd="z"
alias cat="bat"
alias py="python"
alias icat="kitten icat"
alias dsize="du -hs"
alias open="xdg-open"
alias man="BAT_THEME='default' batman"

alias l="eza --icons  -a --group-directories-first -1" #EZA_ICON_SPACING=2
alias ll="eza --icons  -a --group-directories-first -1 --no-user --long"
alias tree="eza --icons --tree --group-directories-first"

# Nixos
alias ns="nom-shell --run zsh"
alias nix-switch="nh os switch"
alias nix-update="nh os switch --update"
alias nix-clean="nh clean all --keep 5"
alias nix-search="nh search"
alias nix-test="nh os test"

# python
alias piv="python -m venv .venv"
alias psv="source .venv/bin/activate"

# arch migration
alias cal="cal -myw"
alias cp="cp -rv"
alias df="df -h"
alias du="du -h"
alias mkdir="mkdir -p"
alias pingg="ping 8.8.8.8"
alias scroff="xset dpms force off"
alias wtf="dmesg"
alias ytd="yt-dlp"

# Git tool aliases (not duplicating git config aliases)
alias g="lazygit"
alias gf="onefetch --number-of-file-churns 0 --no-color-palette"