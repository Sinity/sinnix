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
      helpers,
      ...
    }:
    let
      nixosConfig = config;
      sinnixCfg = nixosConfig.sinnix;
      capturesRoot = sinnixCfg.paths.capturesRoot;
      cliCoreEnabled = nixosConfig.sinnix.features.cli.core.enable;

      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

      findFlakeRoot = pkgs.writeShellScriptBin "find-flake-root" (builtins.readFile ./find-flake-root.sh);
    in
    lib.mkMerge [
      # ========================================
      # Zsh Configuration
      # ========================================
      (lib.mkIf cfg.zsh.enable {
        home-manager.users.${user} =
          {
            lib,
            config,
            mkDotsFileFor,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            xdg.configFile."zsh/init.zsh".source = mkDotsFile "/zsh/init.zsh";

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

              # Pure-config init (aliases-adjacent shell setup, fzf preview
              # helpers, terminal title hooks) lives in dots/zsh/init.zsh as a
              # live out-of-store symlink (xdg.configFile above) so edits take
              # effect in new shells without a rebuild. Keep this literal
              # (no Nix interpolation) so the sourced path never depends on a
              # store hash.
              initContent = lib.mkBefore ''
                source ~/.config/zsh/init.zsh
              '';

              shellAliases = {
                c = "clear";
                cat = "bat";
                py = "python";
                icat = "kitten icat";
                dsize = "du -hs";
                open = "xdg-open";
                nvim = "nvim --listen /tmp/nvim-$$";
                ccusage = "ccusage";
                marimo-edit = "marimo edit --mcp";
                marimo-edit-remote = "marimo edit --mcp --host 127.0.0.1 --port 2718";
                l = "eza --icons  -a --group-directories-first -1";
                ll = "eza --icons  -a --group-directories-first -1 --no-user --long";
                tree = "eza --icons --tree --group-directories-first";
                mosh-sinity-ephemeral = "mosh --ssh=\"ssh -p 22\" sinity@sinnix-ethereal";
                ns = "nom-shell --run zsh";
                nix-safe = "nix-safe";
                nix-switch = "sudo nix-safe run --accept-flake-config \"$(find-flake-root)#switch\"";
                nix-test-system = "sudo nix-safe run --accept-flake-config \"$(find-flake-root)#test-system\"";
                nix-check = "nix-safe run --accept-flake-config \"$(find-flake-root)#check\"";
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
          {
            lib,
            config,
            mkDotsFileFor,
            ...
          }:
          let
            mkDotsFile = mkDotsFileFor config;
          in
          {
            # Starship settings stay in Nix (not moved to dots/): Stylix's
            # `stylix.targets.starship` merges live theme-derived
            # `palette`/`palettes.base16` keys into this same
            # `programs.starship.settings` attrset, and HM's starship module
            # only supports generating starship.toml from the fully-merged
            # settings (no raw-file passthrough). Bypassing the module would
            # mean hand-copying the current palette into a static dots/ file,
            # which would silently desync from future Stylix scheme changes.
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
            #
            # Settings live in dots/atuin/config.toml (live out-of-store
            # symlink) instead of `programs.atuin.settings`: this host never
            # sets `home.preferXdgDirectories` or enables the atuin daemon, so
            # HM's atuin module contributes no other keys into the merged
            # settings attrset here — safe to fully bypass the module's
            # generated config file. If either of those get enabled later,
            # revisit (they inject logs.dir/daemon settings into the same
            # generated file).
            programs.atuin = {
              enable = true;
              enableNushellIntegration = false;
              enableZshIntegration = true;
              flags = [ "--disable-up-arrow" ];
            };
            xdg.configFile."atuin/config.toml".source = mkDotsFile "/atuin/config.toml";

            # Zoxide (directory jumping)
            programs.zoxide = {
              enable = true;
              enableZshIntegration = true;
              enableNushellIntegration = true;
            };

            # FZF (fuzzy finder)
            #
            # Kept as HM options, not moved to dots/: these fields render into
            # `home.sessionVariables` (FZF_DEFAULT_COMMAND etc.), which HM
            # exports globally (all shells/services), not just zsh. Sourcing
            # them from a zsh-only dots/ file would narrow that to interactive
            # zsh sessions — a real behavior change, not a pure config move.
            programs.fzf = {
              enable = true;
              defaultCommand = "fd --hidden --strip-cwd-prefix --exclude .git";
              defaultOptions = [ "--border='rounded'" ];
              fileWidget.options = [
                "--preview 'if [ -d {} ]; then eza --tree --color=always {} | head -200; else bat -n --color=always --line-range :500 {}; fi'"
              ];
              changeDirWidget = {
                command = "fd --type=d --hidden --strip-cwd-prefix --exclude .git";
                options = [ "--preview 'eza --tree --color=always {} | head -200'" ];
              };
              # Atuin owns Ctrl-R; keep fzf's file and directory widgets only.
              historyWidget.command = "";
              enableZshIntegration = true;
            };
          };
      })

      # ========================================
      # CLI Utilities & Session Config
      # ========================================
      (lib.mkIf cfg.utilities.enable {
        # Persistence for AI tools and dev caches (colocated with their config)
        sinnix.persistence.home = {
          directories = [
            ".cache" # entire cache dir — nix eval, sccache, uv, etc.
            ".cargo" # Rust crate registry + git checkouts
            ".npm" # npm package cache
          ];
        };

        home-manager.users.${user} =
          {
            config,
            pkgs,
            lib,
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
              # why mkForce: home-manager defaults PAGER via programs.zsh
              # (typically `less` without -R). Force the colour-aware form
              # so SGR escapes from rg/bat/git render correctly.
              PAGER = lib.mkForce "less -R";
              MANPAGER = "nvim +Man!";
              PYTHONDONTWRITEBYTECODE = "1";
              SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
              MICRO_TRUECOLOR = "1";
              LD_LIBRARY_PATH = lib.makeLibraryPath [
                pkgs.libGL
                pkgs.libglvnd
              ];
              LYNCHPIN_PYTHON = "${scriptPkgs.lynchpin-python}/bin/lynchpin-python";
              POLYLOGUE_PYTHON = "${scriptPkgs.polylogue-python}/bin/polylogue-python";
            };

            home.packages =
              (with pkgs; [
                ripgrep
                gum
                curlie
                yq
                xh
                neovim
                yazi
                glow
                man-pages
                man-pages-posix
                ncdu
              ])
              ++ lib.optionals (!cliCoreEnabled) (
                with pkgs;
                [
                  bat
                  eza
                  fd
                  dua
                ]
              )
              ++ [
                scriptPkgs.lynchpin-python
                scriptPkgs.polylogue-python
                findFlakeRoot
                scriptPkgs.ccusage
                scriptPkgs.lsp-root
                scriptPkgs.nix-safe
              ];

            programs = lib.optionalAttrs (!cliCoreEnabled) {
              bat = {
                enable = true;
                config.pager = "less -FR";
              };
            };

            xdg.configFile = {
              "nvim".source = mkDotsFile "/nvim";
            };

            home.activation.rebuildBatCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              ${lib.getExe pkgs.bat} cache --build 2>/dev/null || true
            '';

            # Bash integration for direnv
            home.file.".bashrc" = {
              text = ''
                # Only interactive bash shells should hook direnv. Running
                # `direnv export bash` in every spawned bash process makes agent
                # and script-heavy workflows repeatedly re-evaluate flakes.
                case "$-" in
                  *i*) ;;
                  *) return ;;
                esac

                if command -v direnv >/dev/null 2>&1; then
                  eval "$(direnv hook bash)"
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
