{ hostname, config, pkgs, host, ...}: 
{
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
      plugins = [ "git" "python" "man" ];
    };

    initExtraFirst = ''
      DISABLE_AUTO_UPDATE=true
      DISABLE_MAGIC_FUNCTIONS=true
      export "MICRO_TRUECOLOR=1"
    '';

    initExtra = ''
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

      # pywal setup
      # (cat ~/.cache/wallust/sequences &)
      # source ~/.cache/wal/colors.sh
      # source ~/.cache/wal/colors-tty.sh

      # fpath+=~/.zfunc

      # Fix Ctrl+S in terminal
      stty -ixon

      # Function to update terminal title
      update_terminal_title() {
        LAST_CMD=$1
        TITLE="\033]2;$(pwd); $(date "+%Y-%m-%d %H:%M:%S") $LAST_CMD\007"
        echo -ne $TITLE
      }

      # Hook functions
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

      # broot
      # source ~/.config/broot/launcher/bash/br
    '';

    sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      PAGER = "less";
      BROWSER = "floorp";
      TERM = "kitty";
      TERMINAL = "kitty";
      PYTHONDONTWRITEBYTECODE = "1";
      SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
      # OPENAI_API_KEY = "";
      # RAINDROP_API_KEY = "";
      # GTK_THEME = "Adwaita:dark";
      # QT_STYLE_OVERRIDE = "adwaita-dark";
      LD_LIBRARY_PATH = "$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib";
    };

    shellAliases = {
      # Utils
      c = "clear";
      cd = "z";
      tt = "gtrash put";
      cat = "bat";
      py = "python";
      icat = "kitten icat";
      dsize = "du -hs";
      pdf = "tdf";
      open = "xdg-open";
      space = "ncdu";
      man = "BAT_THEME='default' batman";

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

      # mine
      cal = "cal -myw";
      cp = "cp -rv";
      df = "df -h";
      findbig = "ncdu";
      du = "du -h";
      ls = "ls -AhN --color=auto --group-directories-first";
      mkdir = "mkdir -p";
      pingg = "ping 8.8.8.8";
      # ps = "ps --forest -F --ppid 2 -p 1,2 --deselect";
      # rm = "rm -R";
      scroff = "xset dpms force off";
      top = "htop";
      wp = "~/scripts/set_random_wallpaper.sh /mnt/data/content/wallpapers/anime_3440_1440 -a 97";
      wtf = "dmesg";
      ytd = "yt-dlp";
      theme-tool = "java -jar ~/scripts/redacted.jar";
      d = "dunstify --urgency=critical --timeout=60000";
      er = "sudo -e";
    };
  };

  home.sessionPath = [
    "$HOME/scripts"
    "$HOME/scripts/yeelight"
    "$HOME/.local/bin"
    "$HOME/.cargo/bin"
  ];

  programs.zoxide = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.broot = {
    enable = true;
    settings.modal = true;
  };
}
