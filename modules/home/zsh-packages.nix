{...}: {
  # Note: Zsh configuration now managed by dotfiles
  # This file only ensures packages and integrations are installed
  
  home.packages = [
    # Ensure core tools used by Zsh config are available
  ];

  # Keep these enabled to ensure all the integration hooks work properly
  programs.zoxide = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.broot = {
    enable = true;
    settings.modal = true;
  };
  
  home.sessionPath = [
    "$HOME/scripts"
    "$HOME/scripts/yeelight"
  ];
}