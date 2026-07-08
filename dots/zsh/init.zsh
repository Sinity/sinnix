DISABLE_AUTO_UPDATE=true
DISABLE_MAGIC_FUNCTIONS=true
export "MICRO_TRUECOLOR=1"

set -o vi

if [ -z "$NH_FLAKE" ]; then
  export NH_FLAKE="$(find-flake-root)"
fi

show_file_or_dir_preview='if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi'

_fzf_compgen_path() {
  fd --hidden --exclude .git . "$1"
}

_fzf_compgen_dir() {
  fd --type=d --hidden --exclude .git . "$1"
}

_fzf_comprun() {
  local command=$1
  shift

  case "$command" in
    cd)           fzf --preview 'eza --tree --color=always {} | head -200' "$@" ;;
    ssh)          fzf --preview 'dig {}'                   "$@" ;;
    *)            fzf --preview "$show_file_or_dir_preview" "$@" ;;
  esac
}

stty -ixon
unsetopt prompt_sp

update_terminal_title() {
  local last_cmd="$1"
  printf '\033]2;%s; %s\007' "$PWD" "$last_cmd"
}
_terminal_title_preexec() { update_terminal_title "$1" }
_terminal_title_precmd() { update_terminal_title "" }

autoload -U add-zsh-hook
add-zsh-hook preexec _terminal_title_preexec
add-zsh-hook precmd _terminal_title_precmd
zmodload zsh/zpty

autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic
autoload -Uz url-quote-magic
zle -N self-insert url-quote-magic
