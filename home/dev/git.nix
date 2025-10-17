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
      d = "diff --word-diff=color --word-diff-regex=[^[:space:],]+";
      d0 = "diff";
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
      dst = "diff --staged --word-diff=color --word-diff-regex=[^[:space:],]+";
      dwt = "diff --word-diff=color --word-diff-regex=[^[:space:],]+";
      dststat = "diff --staged --stat";
      dstd = "difftool --staged --tool=difftastic --prompt=false";
    };

    extraConfig = {
      init.defaultBranch = "master";
      merge.conflictstyle = "diff3";
      diff.colorMoved = "default";
      delta = {
        line-numbers = true;
        side-by-side = false;
        navigate = true;
      };
      alias.cma = "!git add --all && git commit -m";
      "credential \"https://github.com\"".helper = ''!f(){ if [ -r /run/agenix/github-token ]; then printf 'username=x-access-token\npassword=%s\n' "$(< /run/agenix/github-token)"; fi; }; f'';
      "credential \"https://api.github.com\"".helper = ''!f(){ if [ -r /run/agenix/github-token ]; then printf 'username=x-access-token\npassword=%s\n' "$(< /run/agenix/github-token)"; fi; }; f'';
      difftool.prompt = false;
      "difftool \"difftastic\"".cmd =
        ''difft --display=inline --background=dark --width="$(tput cols)" "$LOCAL" "$REMOTE"'';
    };
  };
}
