# modules/home/git.nix
{pkgs, ...}: {
  programs.git = {
    enable = true;
    # Ensure git and delta are installed if not already via home.packages
    # package = pkgs.git;
    delta.enable = true; # Installs delta and sets it as pager

    userName = "Sinity";
    userEmail = "ezo.dev@gmail.com";

    aliases = {
      # Aliases from your .gitconfig
      a = "add";
      aa = "add --all";
      s = "status";
      b = "branch";
      m = "merge";
      d = "diff";
      pl = "pull";
      plo = "pull origin";
      ps = "push";
      pso = "push origin";
      pst = "push --follow-tags";
      cl = "clone";
      c = "commit";
      cm = "commit -m";
      # For the ! command alias, use extraConfig or a helper script
      # cma = "!git add --all && git commit -m"; # Handled via extraConfig below
      tag = "tag -ma";
      ch = "checkout";
      chb = "checkout -b";
      log = "log --oneline --decorate --graph";
      lol = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset'";
      lola = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --all";
      lols = "log --graph --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%ar) %C(bold blue)<%an>%Creset' --stat";
    };

    extraConfig = {
      init.defaultBranch = "master";
      merge.conflictstyle = "diff3";
      diff.colorMoved = "default";
      # core.pager = "delta"; # Explicitly set, though delta.enable does this
      # interactive.diffFilter = "delta --color-only";

      # Delta specific settings (already set by delta.enable defaults, but can override)
      delta = {
        line-numbers = true;
        side-by-side = true;
        navigate = true;
      };

      # Handle the shell command alias
      alias.cma = "!git add --all && git commit -m";
    };
  };
}
