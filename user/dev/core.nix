{
  lib,
  pkgs,
  inputs,
  ...
}:
let
  flakePath = "${inputs.self}";
in
{
  home.sessionVariables = {
    DEVELOPMENT_DOMAIN = "v0.3";
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

  home.activation.linkNeovimConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p "$HOME/.config"
    ln -sfn ''${FLAKE:-${flakePath}}/dots/nvim "$HOME/.config/nvim"
  '';

  home.activation.ensureClaudeDir = lib.hm.dag.entryAfter [ "linkNeovimConfig" ] ''
    if [ -e "$HOME/.claude" ] && ! [ -L "$HOME/.claude" ]; then
      rm -rf "$HOME/.claude"
    fi
    ln -sfn .config/claude "$HOME/.claude"
  '';

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
