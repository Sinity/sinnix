{ pkgs, ... }:
{
  system.stateVersion = "24.05";

  environment.packages = with pkgs; [
    bat
    curl
    fd
    file
    git
    htop
    jq
    mosh
    neovim
    openssh
    ripgrep
    rsync
    tmux
    tree
    unzip
    wget
    zip
  ];

  environment.sessionVariables = {
    EDITOR = "nvim";
    PAGER = "less -FR";
  };

  android-integration = {
    am.enable = true;
    termux-open.enable = true;
    termux-open-url.enable = true;
    termux-reload-settings.enable = true;
  };

  networking.hosts."100.114.9.64" = [
    "sinnix-prime"
    "sinnix-prime.tail895743.ts.net"
  ];

  home-manager.config = {
    home.stateVersion = "24.05";

    programs = {
      bash = {
        enable = true;
        shellAliases = {
          l = "ls -lah";
          prime = "ssh sinnix-prime";
        };
      };
      git.enable = true;
      neovim = {
        enable = true;
        defaultEditor = true;
        withPython3 = false;
        withRuby = false;
      };
    };
  };
}
