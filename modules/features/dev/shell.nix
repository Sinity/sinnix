# Shell Environment Configuration
#
# Unified shell experience with subFeatures for:
# - zsh: Zsh + oh-my-zsh + completion + syntax highlighting
# - utilities: CLI tools (bat, eza, fd, ripgrep) + session vars + config symlinks
# - tmux: Terminal multiplexer with vi-mode
# - prompt: Starship prompt + Atuin history + Zoxide + FZF
{
  mkFeatureModule,
  lib,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "shell"
  ];
  description = "Advanced shell environment (Zsh/Starship/Atuin)";
  subFeatures = {
    zsh = {
      description = "Zsh shell with oh-my-zsh and plugins";
      default = true;
    };
    prompt = {
      description = "Starship prompt with Atuin history";
      default = true;
    };
    utilities = {
      description = "CLI tools and session configuration";
      default = true;
    };
    tmux = {
      description = "Tmux terminal multiplexer";
      default = true;
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      cfg,
      user,
      inputs,
      ...
    }:
    let
      sinnixCfg = config.sinnix;
      capturesRoot = sinnixCfg.paths.capturesRoot;

      # Script packages from flake registry
      scriptPkgs = inputs.self.packages.${pkgs.stdenv.hostPlatform.system};

      findFlakeRoot = pkgs.writeShellScriptBin "find-flake-root" ''
        #!/usr/bin/env bash
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
    lib.mkMerge [
      # ========================================
      # Zsh Configuration
      # ========================================
      (lib.mkIf cfg.zsh.enable {
        home-manager.users.${user} =
          { lib, ... }:
          {
            programs.zsh = {
              enable = true;
              enableCompletion = true;
              autosuggestion.enable = true;
              syntaxHighlighting.enable = true;
              history = {
                path = "${capturesRoot}/shell/zsh/history";
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
                gemini = "~/.local/bin/gemini";
                marimo-edit = "marimo edit --mcp";
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
                psq = "procs --tree --thread-off";
                wtf = "dmesg";
                ytd = "yt-dlp";
              };
            };
          };
      })

      # ========================================
      # Prompt & History Tools (Starship, Atuin, Zoxide, FZF)
      # ========================================
      (lib.mkIf cfg.prompt.enable {
        home-manager.users.${user} =
          { lib, ... }:
          {
            # Starship Prompt
            programs.starship = {
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

            # Atuin History
            programs.atuin = {
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

            # Zoxide (directory jumping)
            programs.zoxide = {
              enable = true;
              enableZshIntegration = true;
              enableNushellIntegration = true;
            };

            # FZF (fuzzy finder)
            programs.fzf = {
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
      })

      # ========================================
      # CLI Utilities & Session Config
      # ========================================
      (lib.mkIf cfg.utilities.enable {
        home-manager.users.${user} =
          {
            config,
            pkgs,
            lib,
            sinnix,
            mkDotsFileFor,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            home.sessionVariables = {
              EDITOR = "nvim";
              VISUAL = "nvim";
              PAGER = lib.mkForce "less -R";
              MANPAGER = "nvim +Man!";
              PYTHONDONTWRITEBYTECODE = "1";
              SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
              MICRO_TRUECOLOR = "1";
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
                ast-grep
                mprocs
                tmux
                dtach
                weechat
                neovim
                yazi
                glow
                graphviz
                mermaid-cli
                android-tools
                dua
                evtest
                gcc
                gdb
                git-filter-repo
                gnumake
                google-cloud-sdk
                lm_sensors
                man-pages
                man-pages-posix
                meld
                ncdu
                nvitop
                nix-fast-build
                nix-prefetch-git
                nix-tree
                wireshark
                powertop
                nodePackages_latest.bash-language-server
                nodePackages_latest.yaml-language-server
                sysstat
                strace
                polylogue
                gallery-dl
                vulkan-validation-layers
                wayland-utils
                wayland-protocols
              ])
              ++ [
                findFlakeRoot
                scriptPkgs.lsp-root
                scriptPkgs.render-agents
                scriptPkgs.normalize-agent-projects
                scriptPkgs.verify-agent-topology
              ];

            programs = {
              broot = {
                enable = true;
                settings.modal = true;
              };

              bat = {
                enable = true;
                config.pager = "less -FR";
              };
            };

            xdg.configFile = {
              "nvim".source = mkDotsFile "/nvim";
            };

            # Claude Code uses ~/.claude as its single canonical directory.
            # Config files (settings, CLAUDE.md, skills, etc.) live here alongside
            # runtime state (projects/, history.jsonl). Impermanence persists the
            # whole dir; HM manages the config symlinks within it.
            home.file = {
              ".claude/hooks/pretooluse-bash.sh".source = mkDotsFile "/claude/hooks/pretooluse-bash.sh";
              ".claude/settings.json".source = mkDotsFile "/claude/settings.json";
              ".claude/CLAUDE.md".source = mkDotsFile "/claude/CLAUDE.md";
              ".claude/world-model" = {
                source = mkDotsFile "/claude/world-model";
                force = true;
                recursive = true;
              };
              ".claude/operational" = {
                source = mkDotsFile "/claude/operational";
                force = true;
                recursive = true;
              };
              ".claude/skills" = {
                source = mkDotsFile "/claude/skills";
                force = true;
                recursive = true;
              };
            };

            home.activation.rebuildBatCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              ${lib.getExe pkgs.bat} cache --build 2>/dev/null || true
            '';
            home.activation.renderGlobalCodexAgents = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              mkdir -p "$HOME/.codex"
              if [ -f "$HOME/.claude/CLAUDE.md" ]; then
                ${scriptPkgs.render-agents}/bin/render-agents \
                  --input "$HOME/.claude/CLAUDE.md" \
                  --output "$HOME/.codex/AGENTS.md"
              fi
            '';

            # CLI wrappers
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

            home.file.".local/bin/codex" = {
              text = ''
                #!/usr/bin/env bash
                set -euo pipefail

                CODEX_BIN="${inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system}.codex}/bin/codex"
                RENDER_AGENTS_BIN="${scriptPkgs.render-agents}/bin/render-agents"
                if [ ! -x "$RENDER_AGENTS_BIN" ]; then
                  RENDER_AGENTS_BIN="$(command -v render-agents 2>/dev/null || true)"
                fi
                render_instruction_tree() {
                  local root="$1"
                  local dir="$root"
                  while :; do
                    if [ -f "$dir/CLAUDE.md" ]; then
                      if ! "$RENDER_AGENTS_BIN" --input "$dir/CLAUDE.md" --output "$dir/AGENTS.md"; then
                        echo "warning: failed to render $dir/CLAUDE.md" >&2
                      fi
                    fi
                    [ "$dir" = "/" ] && break
                    dir="$(dirname "$dir")"
                  done
                }

                if [ -z "''${SINNIX_SKIP_AGENTS_RENDER:-}" ] && [ -x "$RENDER_AGENTS_BIN" ]; then
                  if [ -f "$HOME/.claude/CLAUDE.md" ]; then
                    "$RENDER_AGENTS_BIN" \
                      --input "$HOME/.claude/CLAUDE.md" \
                      --output "$HOME/.codex/AGENTS.md" || echo "warning: failed to render global CLAUDE.md" >&2
                  fi

                  start_dir="$PWD"
                  argv=("$@")
                  i=0
                  while [ "$i" -lt "''${#argv[@]}" ]; do
                    arg="''${argv[$i]}"
                    case "$arg" in
                      -C|--cd)
                        if [ "$((i + 1))" -lt "''${#argv[@]}" ]; then
                          start_dir="''${argv[$((i + 1))]}"
                          i=$((i + 2))
                          continue
                        fi
                        ;;
                      --cd=*)
                        start_dir="''${arg#--cd=}"
                        ;;
                    esac
                    i=$((i + 1))
                  done

                  if [ -d "$start_dir" ]; then
                    start_dir="$(cd "$start_dir" && pwd -P)"
                    render_instruction_tree "$start_dir"
                  fi
                fi

                exec "$CODEX_BIN" "$@"
              '';
              executable = true;
            };

            home.file.".local/bin/gemini" = {
              text = ''
                #!/usr/bin/env bash
                set -euo pipefail

                GEMINI_BIN="${inputs.self.packages.${pkgs.stdenv.hostPlatform.system}.gemini}/bin/gemini"
                RENDER_AGENTS_BIN="${scriptPkgs.render-agents}/bin/render-agents"

                # Render CLAUDE.md → GEMINI.md for shared instructions
                if [ -f "$HOME/.claude/CLAUDE.md" ] && [ -x "$RENDER_AGENTS_BIN" ]; then
                  "$RENDER_AGENTS_BIN" \
                    --input "$HOME/.claude/CLAUDE.md" \
                    --output "$HOME/.gemini/GEMINI.md" 2>/dev/null || true
                fi

                exec "$GEMINI_BIN" "$@"
              '';
              executable = true;
            };

            home.file.".serena/serena_config.yml".source = mkDotsFile "/serena/serena_config.yml";

            # Bash integration for direnv
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
      })

      # ========================================
      # Tmux Configuration
      # ========================================
      (lib.mkIf cfg.tmux.enable {
        home-manager.users.${user} =
          { config, sinnix, ... }:
          {
            programs.tmux = {
              enable = true;
              baseIndex = 1;
              escapeTime = 0;
              historyLimit = 50000;
              keyMode = "vi";
              mouse = true;
              prefix = "C-Space";
              terminal = "tmux-256color";
              # Source user config via symlink for hot reload (no rebuild needed)
              extraConfig = "source-file ~/.config/tmux/user.conf";
            };

            # Symlink tmux user config for hot reload (edits apply without rebuild)
            xdg.configFile."tmux/user.conf".source =
              config.lib.file.mkOutOfStoreSymlink "${sinnix.paths.dotsRoot}/tmux/tmux.conf";
          };
      })
    ];
} args
