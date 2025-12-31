{
  lib,
  pkgs,
  config,
  ...
}:
let
  cfg = config.sinnix.features.cli.core;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.cli.core = {
    enable = lib.mkEnableOption "Core CLI environment";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { lib, pkgs, ... }: {
      home.packages = lib.mkAfter (
        with pkgs;
        [
          nix-output-monitor
          nvd
          cachix
          nix-direnv
          killall
          procps
          psmisc
          iotop
          entr
          file
          tldr
          xdg-utils
          xxd
          graphicsmagick
        ]
      );

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

      nix.gc = {
        automatic = true;
        dates = "weekly";
        options = "--delete-older-than 30d";
      };
    };
  };
}
