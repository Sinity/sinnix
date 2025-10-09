{ lib, pkgs, ... }:
{
  home.packages = with pkgs; [
    bat
    eza
    fd
    ripgrep
    fzf
    stow
    jq
    yq
    csvtool
    csvkit
    csvq
    httpie
    curlie
    websocat
    xh
    tokei
    diffsitter
    difftastic
    ast-grep
    zellij
    mprocs
    tmux
    neovim
    graphviz
    mermaid-cli
    claude-code-usage-monitor
  ];

  programs = {
    zsh = {
      enable = true;
      enableCompletion = true;
      autosuggestion.enable = true;
      syntaxHighlighting.enable = true;

      history = {
        save = 9999999;
        size = 9999999;
        append = true;
        share = true;
        expireDuplicatesFirst = true;
        extended = true;
        ignoreDups = true;
      };
      historySubstringSearch.enable = true;

      oh-my-zsh = {
        enable = true;
        plugins = [
          "git"
          "python"
          "man"
        ];
      };

      initContent = lib.mkBefore ''
        DISABLE_AUTO_UPDATE=true
        DISABLE_MAGIC_FUNCTIONS=true
        export "MICRO_TRUECOLOR=1"

        set -o vi

        _sinnix_flake_root() {
          if [ -n "$FLAKE" ]; then
            printf '%s\n' "$FLAKE"
            return 0
          fi
          if command -v git >/dev/null 2>&1; then
            if git_root=$(git rev-parse --show-toplevel 2>/dev/null); then
              printf '%s\n' "$git_root"
              return 0
            fi
          fi
          if [ -n "$PRJ_ROOT" ]; then
            printf '%s\n' "$PRJ_ROOT"
            return 0
          fi
          if [ -n "$DEVENV_ROOT" ]; then
            printf '%s\n' "$DEVENV_ROOT"
            return 0
          fi
          printf '%s\n' "$PWD"
        }

        if [ -z "$FLAKE" ]; then
          export FLAKE="$(_sinnix_flake_root)"
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

        autoload -Uz bracketed-paste-magic
        zle -N bracketed-paste bracketed-paste-magic
        autoload -Uz url-quote-magic
        zle -N self-insert url-quote-magic

        eval "$(atuin init zsh --disable-up-arrow)"
      '';

      shellAliases = {
        c = "clear";
        cat = "bat";
        py = "python";
        icat = "kitten icat";
        dsize = "du -hs";
        open = "xdg-open";
        cl = "~/.claude/local/node_modules/.bin/claude";
        claude = "~/.claude/local/node_modules/.bin/claude --add-dir /realm /home/sinity";
        nvim = "nvim --listen /tmp/nvim-$$";
        ccm = "ccmonitor --refresh-rate 1 --refresh-per-second 20";
        ccm-attach = "zellij attach ccusage-monitor";
        ccusage = "npx --yes ccusage@latest";
        gemini-cli = "npx --yes https://github.com/google-gemini/gemini-cli";
        l = "eza --icons  -a --group-directories-first -1";
        ll = "eza --icons  -a --group-directories-first -1 --no-user --long";
        tree = "eza --icons --tree --group-directories-first";
        ns = "nom-shell --run zsh";
        nix-switch = "sudo nix run \"\$(_sinnix_flake_root)#switch\"";
        nix-test = "sudo nix run \"\$(_sinnix_flake_root)#test\"";
        nix-check = "nix run \"\$(_sinnix_flake_root)#check\"";
        nix-search = "nix search nixpkgs";
        piv = "python -m venv .venv";
        psv = "source .venv/bin/activate";
        cal = "cal -myw";
        cp = "cp -rv";
        df = "df -h";
        du = "du -h";
        mkdir = "mkdir -p";
        pingg = "ping 8.8.8.8";
        wtf = "dmesg";
        ytd = "yt-dlp";
      };
    };

    zoxide = {
      enable = true;
      enableZshIntegration = true;
      enableNushellIntegration = true;
    };

    broot = {
      enable = true;
      settings.modal = true;
    };

    atuin = {
      enable = true;
      enableNushellIntegration = false;
      enableZshIntegration = false;
      flags = [ "--disable-up-arrow" ];
      settings = {
        auto_sync = false;
        search_mode = "fuzzy";
        filter_mode = "global";
        style = "compact";
        inline_height = 30;
        up_arrow = false;
        show_preview = true;
        invert = true;
        keymap_mode = "vim-normal";
      };
    };

    bat = {
      enable = true;
      config.pager = "less -FR";
    };

    fzf = {
      enable = true;
      defaultCommand = "fd --hidden --strip-cwd-prefix --exclude .git";
      defaultOptions = [
        "--color=fg:-1,fg+:#FBF1C7,bg:-1,bg+:#282828"
        "--color=hl:#98971A,hl+:#B8BB26,info:#928374,marker:#D65D0E"
        "--color=prompt:#CC241D,spinner:#689D6A,pointer:#D65D0E,header:#458588"
        "--color=border:#665C54,label:#aeaeae,query:#FBF1C7"
        "--border='rounded'"
        "--border-label=''"
        "--preview-window='border-rounded'"
        "--prompt='> '"
        "--marker='>'"
        "--pointer='>'"
        "--separator='─'"
        "--scrollbar='│'"
        "--info='right'"
      ];
      fileWidgetOptions = [
        "--preview 'if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi'"
      ];
      changeDirWidgetCommand = "fd --type=d --hidden --strip-cwd-prefix --exclude .git";
      changeDirWidgetOptions = [ "--preview 'eza --tree --color=always {} | head -200'" ];
      enableZshIntegration = true;
    };
  };
}
