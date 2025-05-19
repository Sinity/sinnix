{
  config,
  lib,
  pkgs,
  ...
}:
{
  home.packages = with pkgs; [ neovim ];

  # Create a symlink to neovim config directory
  # No longer uses the nested dots/nvim structure
  home.activation.linkNeovimConfig = config.lib.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p $HOME/.config
    echo "Creating symlink for Neovim configuration..."
    ln -sfn /realm/nixos-config/nvim $HOME/.config/nvim
  '';
}
