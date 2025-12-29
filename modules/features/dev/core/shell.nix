{
  lib,
  pkgs,
  inputs,
  sinnix,
  config,
  ...
}:
let
  username = sinnix.user.name;
  isDesktop = sinnix.machine.isDesktop;
in
{
  home.packages = with pkgs; [
    bat
    eza
    fd
    ripgrep
    gum
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
    mprocs
    tmux
    neovim
    graphviz
    mermaid-cli

    antigravity # TODO: It's not the greatest placement for this
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

      loginExtra = ''
        if [ "${lib.boolToString isDesktop}" = "true" ] && [ "$(id -un)" = "${username}" ] && [ -z "$DISPLAY" ]; then
          current_tty=$(tty 2>/dev/null || true)
          if [ "$current_tty" = "/dev/tty1" ]; then
            exec uwsm start hyprland-uwsm.desktop
          fi
        fi
      '';

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
        ccm = "ccmonitor --refresh-rate 1 --refresh-per-second 20";
        ccusage = "npx --yes ccusage@latest";
        gemini-cli = "npx --yes https://github.com/google-gemini/gemini-cli";
        marimo-edit = "marimo edit --mcp";
        marimo-edit-remote = "marimo edit --mcp --host 0.0.0.0 --port 2718";
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

  home.file.".local/bin/find-flake-root" = {
    source = ../../../../scripts/find-flake-root;
    executable = true;
  };

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

}
