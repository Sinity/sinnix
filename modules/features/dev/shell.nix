{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
let
  cfg = config.sinnix.features.dev.shell;
  user = config.sinnix.user.name;
  findFlakeRoot = pkgs.writeShellScriptBin "find-flake-root" ''
    #!/usr/bin/env bash
    # Finds the root of the current flake/project context.
    set -euo pipefail

    if [ -n "''${FLAKE:-}" ]; then
      printf '%s\n' "$FLAKE"
      exit 0
    fi
    if command -v git >/dev/null 2>&1; then
      if git_root=$(git rev-parse --show-toplevel 2>/dev/null); then
        printf '%s\n' "$git_root"
        exit 0
      fi
    fi
    if [ -n "''${PRJ_ROOT:-}" ]; then
      printf '%s\n' "$PRJ_ROOT"
      exit 0
    fi
    if [ -n "''${DEVENV_ROOT:-}" ]; then
      printf '%s\n' "$DEVENV_ROOT"
      exit 0
    fi
    printf '%s\n' "$PWD"
  '';
in
{
  options.sinnix.features.dev.shell.enable =
    lib.mkEnableOption "Advanced shell environment (Zsh/Starship/Atuin)";

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} =
      {
        pkgs,
        lib,
        config,
        sinnix,
        ...
      }:
      let
        dotsRoot = sinnix.paths.dotsRoot;
      in
      {
        home.sessionVariables = {
          DEVELOPMENT_DOMAIN = "v0.3";
          EDITOR = "nvim";
          VISUAL = "nvim";
          # Override default pager to enable color output (-R for raw control chars)
          PAGER = lib.mkForce "less -R";
          MANPAGER = "nvim +Man!";
          PYTHONDONTWRITEBYTECODE = "1";
          SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
          MICRO_TRUECOLOR = "1";
          # Disable Qdrant for polylogue (use FTS5 only)
          POLYLOGUE_QDRANT_URL = "";
          LD_LIBRARY_PATH = lib.makeLibraryPath [
            pkgs.libGL
            pkgs.libglvnd
          ];
        };

        home.packages =
          (with pkgs; [
            bat
            eza
            fd
            ripgrep
            gum
            stow
            curlie
            yq
            csvkit
            httpie
            websocat
            xh
            tokei
            diffsitter
            difftastic
            ast-grep
            mprocs
            tmux
            dtach
            neovim
            yazi
            glow
            graphviz
            mermaid-cli
            antigravity
          ])
          ++ [ findFlakeRoot ];

        programs = {
          zsh = {
            enable = true;
            enableCompletion = true;
            autosuggestion.enable = true;
            syntaxHighlighting.enable = true;
            history = {
              path = "${sinnix.paths.capturesRoot}/shell/zsh/history";
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

            initContent = lib.mkMerge [
              (lib.mkBefore ''
                DISABLE_AUTO_UPDATE=true
                DISABLE_MAGIC_FUNCTIONS=true
                export "MICRO_TRUECOLOR=1"

                set -o vi

                if [ -z "$FLAKE" ]; then
                  export FLAKE="$(find-flake-root)"
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
              '')
            ];

            shellAliases = {
              c = "clear";
              cat = "bat";
              py = "python";
              icat = "kitten icat";
              dsize = "du -hs";
              open = "xdg-open";
              cl = "~/.local/bin/claude";
              claude = "~/.local/bin/claude";
              nvim = "nvim --listen /tmp/nvim-$$";
              ccusage = "npx --yes ccusage@latest";
              gemini-cli = "npx --yes https://github.com/google-gemini/gemini-cli --yolo";
              marimo-edit = "marimo edit --mcp";
              # Remote marimo binds to localhost only - use SSH tunnel for external access
              marimo-edit-remote = "marimo edit --mcp --host 127.0.0.1 --port 2718";
              l = "eza --icons  -a --group-directories-first -1";
              ll = "eza --icons  -a --group-directories-first -1 --no-user --long";
              tree = "eza --icons --tree --group-directories-first";
              mosh-sinity-ephemeral = "mosh --ssh=\"ssh -p 22\" sinity@sinnix-ethereal";
              ns = "nom-shell --run zsh";
              nix-switch = "sudo nix run --accept-flake-config \"$(find-flake-root)#switch\"";
              nix-test = "sudo nix run --accept-flake-config \"$(find-flake-root)#test\"";
              nix-check = "nix run --accept-flake-config \"$(find-flake-root)#check\"";
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

          starship = {
            enable = true;
            enableBashIntegration = true;
            enableZshIntegration = true;
            enableNushellIntegration = true;
            settings = {
              add_newline = false;
              format = "$directory $git_branch$git_status$nix_shell$character";
              right_format = "$cmd_duration$jobs$status$time";

              directory = {
                format = "[$path]($style)";
                style = "cyan bold";
                fish_style_pwd_dir_length = 1;
                home_symbol = "~";
                truncate_to_repo = false;
              };

              git_branch = {
                format = "[$branch]($style)";
                style = "yellow";
                only_attached = true;
              };

              git_status = {
                format = "([$all_status$ahead_behind]($style))";
                style = "red";
                conflicted = "=";
                ahead = "⇡";
                behind = "⇣";
                diverged = "⇕";
                untracked = "?";
                stashed = "\\$";
                modified = "*";
                staged = "+";
                renamed = "»";
                deleted = "✘";
              };

              nix_shell = {
                format = "[$symbol]($style)";
                symbol = "N";
                style = "blue bold";
                impure_msg = "[N](red bold)";
                pure_msg = "[N](blue bold)";
              };

              cmd_duration = {
                format = "[$duration]($style)";
                style = "yellow dimmed";
                min_time = 3000;
                show_milliseconds = false;
              };

              character = {
                success_symbol = "[❯](bold green)";
                error_symbol = "[❯](bold red)";
                vimcmd_symbol = "[❮](bold green)";
              };

              time = {
                disabled = false;
                format = "[$time]($style)";
                time_format = "%H:%M";
                style = "dimmed";
              };

              status = {
                disabled = false;
                format = "[$symbol$status]($style)";
                symbol = "✘";
                style = "red";
                map_symbol = true;
                pipestatus = true;
              };

              jobs = {
                format = "[$symbol$number]($style)";
                symbol = "⚡";
                style = "yellow";
                threshold = 1;
              };

              gcloud.disabled = true;
            };
          };

          broot = {
            enable = true;
            settings.modal = true;
          };

          atuin = {
            enable = true;
            enableNushellIntegration = false;
            enableZshIntegration = true;
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
            defaultOptions = [ "--border='rounded'" ];
            fileWidgetOptions = [
              "--preview 'if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi'"
            ];
            changeDirWidgetCommand = "fd --type=d --hidden --strip-cwd-prefix --exclude .git";
            changeDirWidgetOptions = [ "--preview 'eza --tree --color=always {} | head -200'" ];
            enableZshIntegration = true;
          };
        };

        home.activation.linkNeovimConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          mkdir -p "$HOME/.config"
          DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
          ln -sfn "$DOTS_ROOT/nvim" "$HOME/.config/nvim"
        '';

        home.activation.linkClaudeConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
          mkdir -p "$HOME/.config/claude"
          ln -sfn "$DOTS_ROOT/claude/settings.json" "$HOME/.config/claude/settings.json"
          ln -sfn "$DOTS_ROOT/claude/cclsp.json" "$HOME/.config/claude/cclsp.json"
          ln -sfn "$DOTS_ROOT/claude/CLAUDE.md" "$HOME/.config/claude/CLAUDE.md"
          ln -sfn "$DOTS_ROOT/claude/skills" "$HOME/.config/claude/skills"
        '';

        home.activation.ensureClaudeDir = lib.hm.dag.entryAfter [ "linkClaudeConfig" ] ''
          if [ -e "$HOME/.claude" ] && ! [ -L "$HOME/.claude" ]; then
            rm -rf "$HOME/.claude"
          fi
          ln -sfn .config/claude "$HOME/.claude"
        '';

        home.activation.linkSerenaConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
          DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
          mkdir -p "$HOME/.serena"
          ln -sfn "$DOTS_ROOT/serena/serena_config.yml" "$HOME/.serena/serena_config.yml"
        '';

        # Always rebuild bat cache - version upgrades on unstable invalidate it
        home.activation.rebuildBatCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
          ${lib.getExe pkgs.bat} cache --build 2>/dev/null || true
        '';

        home.file.".local/bin/claude" = {
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            CLAUDE_BIN="${
              inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system}.claude-code
            }/bin/claude"
            REALM_DIR="${sinnix.paths.realmRoot}"
            HOME_DIR="${config.home.homeDirectory}"

            if [ -d "$REALM_DIR" ]; then
              exec "$CLAUDE_BIN" --add-dir "$REALM_DIR" "$HOME_DIR" "$@"
            else
              exec "$CLAUDE_BIN" "$HOME_DIR" "$@"
            fi
          '';
          executable = true;
        };

        home.file.".bashrc" = {
          text = ''
            # Automatically load direnv-provided environment for any bash shell
            if command -v direnv >/dev/null 2>&1; then
              eval "$(direnv export bash)" || true
            fi
          '';
        };

        home.file.".bash_profile" = {
          text = ''
            if [ -f "$HOME/.bashrc" ]; then
              . "$HOME/.bashrc"
            fi
          '';
        };
      };
  };
}
