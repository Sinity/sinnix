{
  lib,
  pkgs,
  sinnix,
  ...
}:
let
  dotsRoot = "${sinnix.paths.dotsRoot}";
in
{
  home = {
    sessionVariables = {
      DEVELOPMENT_DOMAIN = "v0.3";
      EDITOR = "nvim";
      VISUAL = "nvim";
      PAGER = lib.mkForce "less -R";
      MANPAGER = "nvim +Man!";
      POLYLOGUE_CONFIG = "/realm/data/chatlog/config/config.json";
      PYTHONDONTWRITEBYTECODE = "1";
      SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0";
      MICRO_TRUECOLOR = "1";
      LD_LIBRARY_PATH = lib.makeLibraryPath [
        pkgs.libGL
        pkgs.libglvnd
      ];
    };

    activation = {
      linkNeovimConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        mkdir -p "$HOME/.config"
        DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
        ln -sfn "$DOTS_ROOT/nvim" "$HOME/.config/nvim"
      '';

      linkClaudeConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
        mkdir -p "$HOME/.config/claude"
        # Link individual Claude config files from dots
        ln -sfn "$DOTS_ROOT/claude/settings.json" "$HOME/.config/claude/settings.json"
        ln -sfn "$DOTS_ROOT/claude/cclsp.json" "$HOME/.config/claude/cclsp.json"
        ln -sfn "$DOTS_ROOT/claude/CLAUDE.md" "$HOME/.config/claude/CLAUDE.md"
      '';

      ensureClaudeDir = lib.hm.dag.entryAfter [ "linkClaudeConfig" ] ''
        if [ -e "$HOME/.claude" ] && ! [ -L "$HOME/.claude" ]; then
          rm -rf "$HOME/.claude"
        fi
        ln -sfn .config/claude "$HOME/.claude"
      '';

      linkSerenaConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        DOTS_ROOT=''${DOTS_ROOT:-${dotsRoot}}
        mkdir -p "$HOME/.serena"
        ln -sfn "$DOTS_ROOT/serena/serena_config.yml" "$HOME/.serena/serena_config.yml"
      '';

    };
  };

  programs.direnv = {
    enable = true;
    nix-direnv.enable = true;
    silent = true;
  };

  programs.btop = {
    enable = true;
    settings = {
      vim_keys = true;
      update_ms = 2000;
      show_cpu_freq = true;
      show_gpu = true;
      mem_graphs = true;
      proc_sorting = "cpu direct";
      proc_filter = false;
      tree_view = false;
      proc_per_core = true;
      proc_mem_bytes = true;
      cpu_graph_upper = "total";
      cpu_graph_lower = "user";
      cpu_invert_lower = true;
    };
  };
}
