{lib, ...}: {
  programs.zsh = {
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
      plugins = ["git" "python" "man"];
    };

    # Combined initExtraFirst and initExtra into initContent
    # Use lib.mkBefore for content that should come first
    initContent = lib.mkBefore ''
      DISABLE_AUTO_UPDATE=true
      DISABLE_MAGIC_FUNCTIONS=true
      export "MICRO_TRUECOLOR=1"

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
    ''; # End of initContent

    # Removed deprecated initExtraFirst and initExtra

    sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      PAGER = "less";
      BROWSER = "google-chrome-stable";
      TERM = "kitty";
      TERMINAL = "kitty";

      NH_FLAKE = "/home/sinity/realm/nixos-config";

      PYTHONDONTWRITEBYTECODE = "1";
      SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
      LD_LIBRARY_PATH = "$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib";
    };

    shellAliases = {
      # Utils
      c = "clear";
      cd = "z";
      cat = "bat";
      py = "python";
      icat = "kitten icat";
      dsize = "du -hs";
      open = "xdg-open";

      l = "eza --icons  -a --group-directories-first -1"; #EZA_ICON_SPACING=2
      ll = "eza --icons  -a --group-directories-first -1 --no-user --long";
      tree = "eza --icons --tree --group-directories-first";

      # Nixos
      ns = "nom-shell --run zsh";
      nix-switch = "nh os switch";
      nix-update = "nh os switch --update";
      nix-clean = "nh clean all --keep 5";
      nix-search = "nh search";
      nix-test = "nh os test";

      # python
      piv = "python -m venv .venv";
      psv = "source .venv/bin/activate";

      # arch migration
      cal = "cal -myw";
      cp = "cp -rv";
      df = "df -h";
      du = "du -h";
      mkdir = "mkdir -p";
      pingg = "ping 8.8.8.8";
      scroff = "xset dpms force off";
      wtf = "dmesg";
      ytd = "yt-dlp";
    };
  };

  home.sessionPath = [
    "$HOME/scripts"
    "$HOME/scripts/yeelight"
  ];

  programs.zoxide = {
    enable = true;
    enableZshIntegration = true;
    enableNushellIntegration = true;
  };

  programs.broot = {
    enable = true;
    settings.modal = true;
  };

  programs.atuin = {
    enable = true;
    enableNushellIntegration = false; # Handle nushell separately via dotfiles
    enableZshIntegration = true;
    settings = {
      auto_sync = false;
      search_mode = "fuzzy"; # Or "prefix", "fulltext"
      filter_mode = "host";
      style = "compact";
      inline_height = 30; # number of lines for inline history Ctrl+R
      show_preview = true; # Show command preview in search UI
      invert = true; # Search UI layout preference
      keymap_mode = "auto"; # Default key map style
      up_arrow_key_binding = false; # Disable up arrow for atuin search, keep normal behavior
    };
  };
}
