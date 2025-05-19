# Rofi configuration module
{
  pkgs,
  lib,
  config,
  ...
}:
{
  # Rofi configuration
  programs.rofi = {
    enable = true;
    package = pkgs.rofi-wayland;
    terminal = "${pkgs.kitty}/bin/kitty";
    theme = "gruvbox-dark";
    font = "JetBrainsMono Nerd Font 12";
    extraConfig = {
      modi = "drun,run,filebrowser";
      icon-theme = "Papirus-Dark";
      show-icons = true;
      drun-display-format = "{name}";
      disable-history = false;
      hide-scrollbar = true;
      display-drun = "  Apps ";
      display-run = "  Run ";
      display-filebrowser = "  Files ";
      sidebar-mode = true;
    };
  };
}
