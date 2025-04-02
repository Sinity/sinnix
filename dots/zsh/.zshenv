# XDG Base Directory paths
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache" 
export XDG_DATA_HOME="$HOME/.local/share"

# Use XDG paths for Zsh
export ZDOTDIR="$XDG_CONFIG_HOME/zsh"

# Keep history in home directory
export HISTFILE="$HOME/.zsh_history"

# Create required directories 
[ -d "$ZDOTDIR" ] || mkdir -p "$ZDOTDIR"
[ -d "$XDG_CACHE_HOME" ] || mkdir -p "$XDG_CACHE_HOME"
[ -d "$XDG_DATA_HOME" ] || mkdir -p "$XDG_DATA_HOME"