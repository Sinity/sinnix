{
  inputs,
  pkgs,
  config,
  lib,
  ...
}: {
  # This file contains packages that don't fit neatly into other categories
  # Most packages have been moved to more specialized modules:
  # - development.nix: Development tools
  # - system.nix: System utilities
  # - media.nix: Media applications
  # - desktop-apps.nix: GUI applications

  home.packages = with pkgs; [
    # GTK Themeing Packages
    (gruvbox-gtk-theme.override {colorVariants = ["dark"];})
    (papirus-icon-theme.override {color = "black";})
    bibata-cursors

    # Dotfiles related (kept for transition period)
    stow # Will be removed after complete migration from GNU Stow

    # Fonts
    fira-code # Monospaced font with programming ligatures
    hack-font # Patched font Hack from nerd fonts library

    # wallust
    # screen-pipe
    # crane
    imgur-screenshot
    usbview
    strace
    ltrace
    nvitop
    cage
    wayland-protocols
    vkmark
    dtach
    lnch
    at
    soundwireserver

    weechat
  ];
}
