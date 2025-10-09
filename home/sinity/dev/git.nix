{
  programs.git = {
    enable = true;
    delta.enable = true;
    userName = "Sinity";
    userEmail = "ezo.dev@gmail.com";

    aliases = {
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
      tag = "tag -a";
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
      delta = {
        line-numbers = true;
        side-by-side = true;
        navigate = true;
      };
      alias.cma = "!git add --all && git commit -m";
    };
  };
}
