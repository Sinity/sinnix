# Shell environment: zsh, prompt (Starship/Atuin/Zoxide/FZF), CLI utilities
# and session variables, and tmux — each a separately toggleable subFeature.
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
  # Gated only by the top-level enable, not per-subFeature: every subFeature
  # below defaults to true and no host disables one individually, so this
  # matches current behavior; if that ever changes, a disabled subFeature's
  # dotfile symlink would still be created (harmless but unused).
  meta.dotfiles.configFile = {
    "zsh/init.zsh" = "zsh/init.zsh";
    "atuin/config.toml" = "atuin/config.toml";
    "nvim" = "nvim";
    "tmux/user.conf" = "tmux/tmux.conf";
  };
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
      lakeRoot = sinnixCfg.paths.activityRoot;
      cliCoreEnabled = nixosConfig.sinnix.features.cli.core.enable;

      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

      findFlakeRoot = pkgs.writeShellScriptBin "find-flake-root" (builtins.readFile ./find-flake-root.sh);
    in
    lib.mkMerge [
      # Zsh Configuration
      (lib.mkIf cfg.zsh.enable {
        home-manager.users.${user} =
          {
            lib,
            config,
            ...
          }:
          {
            programs.zsh = {
              enable = true;
              enableCompletion = true;
              autosuggestion.enable = true;
              syntaxHighlighting.enable = true;
              history = {
                path = "${lakeRoot}/shell/zsh/history";
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
              # live out-of-store symlink (meta.dotfiles above) so edits take
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

      # Prompt & History Tools (Starship, Atuin, Zoxide, FZF)
      (lib.mkIf cfg.prompt.enable {
        home-manager.users.${user} =
          {
            lib,
            config,
            ...
          }:
          {
            # Starship settings stay in Nix rather than dots/: Stylix's
            # `stylix.targets.starship` merges theme-derived palette keys into
            # this same settings attrset, and HM's starship module has no
            # raw-file passthrough. A static dots/ file would desync from
            # future Stylix scheme changes.
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

            # Atuin settings live in dots/atuin/config.toml (out-of-store
            # symlink) instead of `programs.atuin.settings`. Safe only while
            # `home.preferXdgDirectories` and the atuin daemon stay off — both
            # inject logs.dir/daemon keys into the module-generated file that
            # this bypasses.
            programs.atuin = {
              enable = true;
              enableNushellIntegration = false;
              enableZshIntegration = true;
              flags = [ "--disable-up-arrow" ];
            };

            # Zoxide (directory jumping)
            programs.zoxide = {
              enable = true;
              enableZshIntegration = true;
              enableNushellIntegration = true;
            };

            # FZF stays in HM options rather than dots/: these fields render
            # into `home.sessionVariables` (FZF_DEFAULT_COMMAND etc.), which HM
            # exports to all shells and services. A zsh-only dots/ file would
            # narrow that to interactive zsh sessions.
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

      # CLI Utilities & Session Config
      (lib.mkIf cfg.utilities.enable {
        # Persistence for AI tools and dev caches (colocated with their config)
        sinnix.persistence.home = {
          directories = [
            ".cache" # entire cache dir — nix eval, uv, etc.
            ".cargo" # Rust crate registry + git checkouts
            ".npm" # npm package cache
          ];
        };

        home-manager.users.${user} =
          {
            config,
            pkgs,
            lib,
            ...
          }:
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

            home.activation.rebuildBatCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
              ${lib.getExe pkgs.bat} cache --build 2>/dev/null || true
            '';

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

      # Tmux Configuration
      (lib.mkIf cfg.tmux.enable {
        home-manager.users.${user} = {
          programs.tmux = {
            enable = true;
            baseIndex = 1;
            escapeTime = 0;
            historyLimit = 50000;
            keyMode = "vi";
            mouse = true;
            prefix = "C-Space";
            terminal = "tmux-256color";
            # Sourced from an out-of-store symlink (meta.dotfiles above) so
            # edits hot-reload without a rebuild.
            extraConfig = "source-file ~/.config/tmux/user.conf";
          };
        };
      })
    ];
} args
