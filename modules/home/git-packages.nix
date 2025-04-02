{ pkgs, ... }:
{
  # Note: Git and SSH configuration now managed by dotfiles
  # This file only ensures packages are installed

  programs.ssh = {
    enable = true;
    matchBlocks."github.com".identityFile = "~/.ssh/id_ed25519"; # TODO: look into secret mgmt solutions like agenix or secrix.
  };

  home.packages = with pkgs; [ 
    gh     # GitHub CLI
    git    # Git version control
    git-delta # Better diffs
    lazygit # TUI for git
    onefetch # Git repo stats 
  ];
}