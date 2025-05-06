# modules/home/shell.nix
{
  pkgs,
  lib,
  config,
  ...
}: {
  # --- Bat Config ---
  programs.bat = {
    enable = true;
    # Add related tools
    extraPackages = with pkgs; [
      # batman
      # batpipe
      # batgrep
    ];
    config = {
      theme = "gruvbox-dark";
      pager = "less -FR";
    };
    # Ensure bat is installed if not already via home.packages
    # package = pkgs.bat;
  };

  # --- FZF Config (from former fzf.nix) ---
  programs.fzf = {
    enable = true;
    # Ensure fzf is installed if not already via home.packages
    # package = pkgs.fzf;

    # Corresponds to FZF_DEFAULT_COMMAND
    defaultCommand = "fd --hidden --strip-cwd-prefix --exclude .git";

    # Corresponds to FZF_DEFAULT_OPTS
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

    # Options for CTRL-T file widget
    fileWidgetOptions = [
      "--preview 'if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi'"
    ];

    # Options for ALT-C directory widget command and preview
    changeDirWidgetCommand = "fd --type=d --hidden --strip-cwd-prefix --exclude .git";
    changeDirWidgetOptions = [
      "--preview 'eza --tree --color=always {} | head -200'"
    ];

    # Enable integrations for shells you use
    enableZshIntegration = true;
    # enableNushellIntegration = true; # Handled separately via dotfiles
    # enableBashIntegration = true;
  };

  # --- Zsh Config (from former zsh.nix) ---
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

    initContent = lib.mkBefore ''
      DISABLE_AUTO_UPDATE=true
      DISABLE_MAGIC_FUNCTIONS=true
      export "MICRO_TRUECOLOR=1"

      # use vi-like keybinds in shell
      set -o vi

      # Use fd (https://github.com/sharkdp/fd) for listing path candidates.
      _fzf_compgen_path() {
        fd --hidden --exclude .git . "$1"
      }

      # Use fd to generate the list for directory completion
      _fzf_compgen_dir() {
        fd --type=d --hidden --exclude .git . "$1"
      }

      # Advanced customization of fzf options via _fzf_comprun function
      _fzf_comprun() {
        local command=$1
        shift

        case "$command" in
          cd)           fzf --preview 'eza --tree --color=always {} | head -200' "$@" ;;
          ssh)          fzf --preview 'dig {}'                   "$@" ;;
          *)            fzf --preview "$show_file_or_dir_preview" "$@" ;; # Needs show_file_or_dir_preview defined
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

    sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      PAGER = "less";
      BROWSER = "google-chrome-stable";
      TERM = "kitty";
      TERMINAL = "kitty";

      NH_FLAKE = "/realm/nixos-config";

      PYTHONDONTWRITEBYTECODE = "1";
      SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
      LD_LIBRARY_PATH = "$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib"; # This might be better set system-wide or via nix-ld
    };

    shellAliases = {
      # Utils
      c = "clear";
      cd = "z"; # Assuming zoxide is used
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
      scroff = "xset dpms force off"; # Note: xset is for X11, won't work in Wayland
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
    enableNushellIntegration = true; # Keep this if you also use Nushell
  };

  programs.broot = {
    enable = true;
    settings.modal = true;
  };

  programs.atuin = {
    enable = true;
    enableNushellIntegration = true; # Enable HM integration
    enableZshIntegration = true;
    settings = {
      auto_sync = false; # Keep sync manual or handle via systemd service if desired
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

  # --- Starship Config (from former starship.nix) ---
  programs.starship = {
    enable = true;

    enableBashIntegration = true; # Keep if you might use Bash
    enableZshIntegration = true;
    enableNushellIntegration = true; # Keep if you use Nushell

    settings = {
      format = lib.concatStrings [
        "[](color_orange)"
        "$os"
        "[](bg:color_yellow fg:color_orange)"
        "$directory"
        "[](fg:color_yellow bg:color_aqua)"
        "$git_branch"
        "$git_status"
        "[](fg:color_aqua bg:color_blue)"
        "$nix_shell"
        "[](fg:color_blue bg:color_bg3)"
        "$cmd_duration"
        "[](fg:color_bg3) "
      ];

      palette = "gruvbox_dark";
      palettes.gruvbox_dark = {
        color_fg0 = "#fbf1c7";
        color_bg1 = "#3c3836";
        color_bg3 = "#665c54";
        color_blue = "#458588";
        color_aqua = "#689d6a";
        color_green = "#98971a";
        color_orange = "#d65d0e";
        color_purple = "#b16286";
        color_red = "#cc241d";
        color_yellow = "#d79921";
      };

      os = {
        disabled = false;
        style = "bg:color_orange bold fg:color_fg0";
        symbols = {
          NixOS = " ";
        };
      };

      directory = {
        style = "bold fg:color_fg0 bg:color_yellow";
        format = "[ $path ]($style)";
        truncation_length = 3;
      };

      git_branch = {
        symbol = "";
        style = "bg:color_aqua";
        format = "[[ $symbol $branch ](bold fg:color_fg0 bg:color_aqua)]($style)";
      };

      git_status = {
        style = "bg:color_aqua bold fg:color_fg0";
        format = "[$all_status$ahead_behind]($style)";
      };

      nix_shell = {
        format = "[ via nix $name ]($style)";
        style = "bg:color_blue bold fg:color_fg0";
      };

      time = {
        disabled = false;
        time_format = "%R";
        style = "bg:color_bg1";
        format = "[[   $time ](fg:color_fg0 bg:color_bg1)]($style)";
      };

      cmd_duration = {
        format = "[ 󰔛 $duration ]($style)";
        disabled = false;
        style = "bg:color_bg3 fg:color_fg0";
        show_notifications = false;
        min_time_to_notify = 60000;
      };

      line_break = {
        disabled = false;
      };

      character = {
        disabled = false;
        success_symbol = "[  ](bold fg:color_green)";
        error_symbol = "[  ](bold fg:color_red)";
      };
    };
  };

  # --- Nushell Config (moved from dots/nushell) ---
  programs.nushell = {
    enable = true;
    # package = pkgs.nushellFull; # Use if extra features needed, default is usually fine

    # Basic environment variables from env.nu
    environmentVariables = {
      NU_FLAKE = "/realm/nixos-config";
      PYTHONDONTWRITEBYTECODE = "1";
      SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
      MICRO_TRUECOLOR = "1";

      AIDER_OPENAI_API_KEY = "$OPENAI_API_KEY";
      AIDER_ANTHROPIC_API_KEY = "$ANTHROPIC_API_KEY";
      AIDER_MODEL = "gemini/gemini-2.5-flash-preview-04-17";
    };

    # Basic config settings from env.nu
    settings = {
      show_banner = false;
      edit_mode = "vi";
      completions = {
        case_sensitive = false;
        quick = true;
        partial = true;
      };
    };

    # Aliases from config.nu
    shellAliases = {
      # Basic utilities
      c = "clear";
      cat = "bat"; # Assumes bat is installed and preferred
      py = "python";
      icat = "kitten icat"; # Assumes kitty is installed

      # Enhanced ls (eza)
      ls = "ls -a"; # Note: `ls` might conflict if eza isn't aliased globally. Consider `alias ls = eza -a`
      ll = "ls -l"; # Consider `alias ll = eza -l`
      tree = "eza --icons --tree --group-directories-first"; # Assumes eza is installed

      # NixOS commands (relies on nh being available)
      nix-switch = "nh os switch";
      nix-update = "nh os switch --update";
      nix-clean = "nh clean all --keep 5";
      nix-search = "nh search";
      nix-test = "nh os test";

      # Other explicit utilities
      pingg = "^ping 8.8.8.8"; # Using ^ for external command
      wtf = "^dmesg";
      ytd = "yt-dlp"; # Assumes yt-dlp is installed
    };

    # Startup tasks from config.nu
    extraConfig = ''
      # Prevent Ctrl+S terminal freezing (safe wrapped call)
      try {
        ^stty -ixon
      } catch {
        print $"[Warn] stty -ixon failed: ($in)"
      }

      # Make sure directory exists for asciinema
      mkdir ~/.asciinema_recordings | ignore

      # Record terminal sessions w/ asciinema (Conditional logic might be complex here)
      # This logic might be better suited for a manual start or a separate script.
      # if ($env.ASCIINEMA_REC? | is-empty) {
      #   mkdir /realm/asciinema_recordings | ignore
      #   let timestamp = (date now | format date '%Y-%m-%d_%H-%M-%S')
      #   let file = $"/realm/asciinema_recordings/($timestamp).cast"
      #   # Ensure asciinema is in PATH
      #   # Using ^ might be needed if not aliased/wrapped
      #   # Consider backgrounding this: exec nohup asciinema rec -c nu $file &
      #   # exec asciinema rec -c nu $file | ignore
      # }
    '';
  };
}
