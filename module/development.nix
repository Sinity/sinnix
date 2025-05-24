# Development Domain Module
# Complete dev workflow (tools + environment)
# Consolidates: programming languages, dev tools, editors, git, nix-ld

{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
{
  config = {
    system.nixos.tags = [ "development-domain-v0.3" ];

    # Core development packages available system-wide
    environment.systemPackages = with pkgs; [
      # Essential development tools
      git
      gnumake
      gcc
      gdb

      # Nix development
      nix-diff
      nix-tree
      nix-prefetch-git

      # Build systems
      cmake
      meson
      ninja
      uv

      # Documentation
      man-pages
      man-pages-posix
    ];

    # nix-ld configuration for running unpatched binaries
    programs.nix-ld = {
      enable = true;
      libraries = with pkgs; [
        # Original libraries
        stdenv.cc.cc
        openssl
        curl
        glib
        util-linux
        glibc
        icu
        libunwind
        libuuid
        zlib
        libsecret
        freetype
        libglvnd
        libnotify
        SDL2
        vulkan-loader
        gdk-pixbuf
        pipewire
        pulseaudio

        alsa-lib
        at-spi2-atk
        at-spi2-core
        atk
        cairo
        cups
        dbus
        expat
        fontconfig
        fuse3
        gtk3
        libGL
        libappindicator-gtk3
        libdrm
        libpulseaudio
        libuuid
        nspr
        nss
        pango
        systemd
        xorg.libX11
        xorg.libXScrnSaver
        xorg.libXcomposite
        xorg.libXcursor
        xorg.libXdamage
        xorg.libXext
        xorg.libXfixes
        xorg.libXi
        xorg.libXrandr
        xorg.libXrender
        xorg.libXtst
        xorg.libxcb
        xorg.libxkbfile
        xorg.libxshmfence
      ];
    };

    home-manager.users.sinity = {
      imports = [
        inputs.claude-code-logger.homeManagerModules.default
      ];

      # Consolidate all home configuration
      home = {
        # Development environment variables
        sessionVariables = {
          DEVELOPMENT_DOMAIN = "v0.3";

          # Development settings from environment.nix
          EDITOR = "nvim";
          VISUAL = "nvim";
          PAGER = lib.mkForce "less -R";
          MANPAGER = "nvim +Man!";
          PYTHONDONTWRITEBYTECODE = "1";
          SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
          MICRO_TRUECOLOR = "1";
          LD_LIBRARY_PATH = "$(nix build --print-out-paths --no-link nixpkgs#libGL)/lib";
        };

        # Consolidated development packages
        packages = with pkgs; [
          # Language Servers, Formatters, Linters
          # Shell tools
          bat
          eza
          fd
          ripgrep
          fzf

          # Dotfiles management (from packages.nix)
          stow # For transitioning from GNU Stow

          markdown-oxide # Used by obsidian.nvim
          nixfmt-rfc-style # Preferred Nix formatter
          nixd
          nil
          nix-diff

          # Rust development
          rustup
          cargo-fuzz
          cargo-bump
          cargo-audit

          # JavaScript/Node.js
          nodejs
          nodejs_latest

          # Python
          python3
          python3Packages.pip
          python312Packages.ipython

          # Database tools
          sqlite
          sqlitebrowser
          sqlite-vec
          sqlite-utils
          sqlitestudio

          # AI development tools
          aider-chat # aider-chat-full # Temporarily disabled due to spacy dependency issues
          claude-code
          inputs.claude-squad.packages.${pkgs.system}.default # Manage multiple AI coding assistants
          claude-desktop-wayland
          codex
          openai-whisper-cpp

          # Development utilities
          jq
          yq
          csvtool
          csvkit
          csvq
          httpie
          curlie
          websocat

          # Git tools
          gh # GitHub CLI
          delta
          lazygit # TUI for git
          onefetch # Git repo stats
          gitui

          # Editor
          neovim
        ];

        # Neovim configuration link
        activation.linkNeovimConfig =
          config.home-manager.users.sinity.lib.dag.entryAfter [ "writeBoundary" ]
            ''
              mkdir -p $HOME/.config
              echo "Creating symlink for Neovim configuration..."
              ln -sfn /realm/nixos-config/nvim $HOME/.config/nvim
            '';
      };

      programs = {
        claude-code-logger = {
          enable = true;
          logDir = "/realm/observability/claude-code-api-log";
          enableSessionFolders = true;
          enableConversationGrouping = true;
          maxInteractionsPerFile = 100;
          maxLogSizeMB = 10;
          createAlias = true;
        };

        # === SHELL CONFIGURATION (from home/environment.nix) ===
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
          '';

          shellAliases = {
            # Utils
            c = "clear";
            cat = "bat";
            py = "python";
            icat = "kitten icat";
            dsize = "du -hs";
            open = "xdg-open";

            l = "eza --icons  -a --group-directories-first -1"; # EZA_ICON_SPACING=2
            ll = "eza --icons  -a --group-directories-first -1 --no-user --long";
            tree = "eza --icons --tree --group-directories-first";

            # NixOS operations using flake apps
            ns = "nom-shell --run zsh";
            nix-switch = "sudo nix run $FLAKE#switch";
            nix-test = "sudo nix run $FLAKE#test";
            nix-check = "nix run $FLAKE#check";

            # Package search
            nix-search = "nix search nixpkgs";

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
          enableNushellIntegration = true;
          enableZshIntegration = true;
          settings = {
            auto_sync = false;
            search_mode = "fuzzy";
            filter_mode = "host";
            style = "compact";
            inline_height = 30;
            show_preview = true;
            invert = true;
            keymap_mode = "auto";
          };
        };

        bat = {
          enable = true;
          config = {
            theme = "gruvbox-dark";
            pager = "less -FR";
          };
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

        starship = {
          enable = true;
          enableBashIntegration = true;
          enableZshIntegration = true;
          enableNushellIntegration = true;

          settings = {
            format = lib.concatStrings [
              "[](color_orange)"
              "$os"
              "[](bg:color_yellow fg:color_orange)"
              "$directory"
              "[](fg:color_yellow bg:color_aqua)"
              "$git_branch"
              "$git_status"
              "[](fg:color_aqua bg:color_blue)"
              "$nix_shell"
              "[](fg:color_blue bg:color_bg3)"
              "$cmd_duration"
              "[](fg:color_bg3) "
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
                NixOS = " ";
              };
            };

            directory = {
              style = "bold fg:color_fg0 bg:color_yellow";
              format = "[ $path ]($style)";
              truncation_length = 3;
            };

            git_branch = {
              symbol = "";
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
              format = "[[   $time ](fg:color_fg0 bg:color_bg1)]($style)";
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
              success_symbol = "[  ](bold fg:color_green)";
              error_symbol = "[  ](bold fg:color_red)";
            };
          };
        };

        nushell = {
          enable = true;
          environmentVariables = {
            AIDER_OPENAI_API_KEY = "$OPENAI_API_KEY";
            AIDER_ANTHROPIC_API_KEY = "$ANTHROPIC_API_KEY";
            AIDER_MODEL = "gemini/gemini-2.5-flash-preview-04-17";
            MICRO_TRUECOLOR = "1";
          };

          settings = {
            show_banner = false;
            edit_mode = "vi";
            completions = {
              case_sensitive = false;
              quick = true;
              partial = true;
            };
          };

          shellAliases = {
            # Basic utilities
            c = "clear";
            cat = "bat";
            py = "python";
            icat = "kitten icat";
            dsize = "du -hs";
            open = "xdg-open";

            # Enhanced ls (eza)
            l = "eza --icons -a --group-directories-first -1";
            ll = "eza --icons -a --group-directories-first -1 --no-user --long";
            tree = "eza --icons --tree --group-directories-first";

            # NixOS operations using flake apps
            nix-switch = "sudo nix run $env.FLAKE#switch";
            nix-test = "sudo nix run $env.FLAKE#test";
            nix-check = "nix run $env.FLAKE#check";

            # Package search
            nix-search = "nix search nixpkgs";

            # Python
            piv = "python -m venv .venv";
            psv = "source .venv/bin/activate";

            # Other utilities
            pingg = "^ping 8.8.8.8";
            wtf = "^dmesg";
            ytd = "yt-dlp";
          };

          extraConfig = ''
            # Prevent Ctrl+S terminal freezing (safe wrapped call)
            try {
              ^stty -ixon
            } catch {
              print $"[Warn] stty -ixon failed: ($in)"
            }

            # Make sure directory exists for asciinema
            mkdir ~/.asciinema_recordings | ignore
          '';
        };

        git = {
          enable = true;
          delta.enable = true; # Installs delta and sets it as pager

          userName = "Sinity";
          userEmail = "ezo.dev@gmail.com";

          aliases = {
            a = "add";
            aa = "add --all";
            s = "status";
            b = "branch";
            m = "merge";
            d = "diff";
            pl = "pull";
            plo = "pull origin";
            ps = "push";
            pso = "push origin";
            pst = "push --follow-tags";
            cl = "clone";
            c = "commit";
            cm = "commit -m";
            tag = "tag -ma";
            ch = "checkout";
            chb = "checkout -b";
            log = "log --oneline --decorate --graph";
            lol = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset'";
            lola = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --all";
            lols = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --stat";
          };

          extraConfig = {
            init.defaultBranch = "master";
            merge.conflictstyle = "diff3";
            diff.colorMoved = "default";

            delta = {
              line-numbers = true;
              side-by-side = true;
              navigate = true;
            };

            alias.cma = "!git add --all && git commit -m";
          };
        };
      };
    };
  };
}
