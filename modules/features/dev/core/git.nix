{ secretPaths, ... }:
let
  githubTokenPath = secretPaths."github-token";
  githubHelper = ''!f(){ if [ -r ${githubTokenPath} ]; then printf 'username=x-access-token\npassword=%s\n' "$(<${githubTokenPath})"; fi; }; f'';
in
{
  programs.git = {
    enable = true;
    settings = {
      user = {
        name = "Sinity";
        email = "ezo.dev@gmail.com";
      };

      alias = {
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
        cma = "!git add --all && git commit -m";
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

        # Clean history views (merge-commits workflow)
        lg = "log --first-parent --oneline --decorate";
        lgg = "log --first-parent --graph --oneline --decorate";
        lga = "log --graph --oneline --decorate --all";
        lgf = "log --graph --oneline --decorate";

        # PR/branch management
        review = "log --first-parent --graph --oneline --decorate @{upstream}..HEAD";
        incoming = "log --first-parent --oneline --decorate ..@{upstream}";
        outgoing = "log --first-parent --oneline --decorate @{upstream}..";

        # Better blame and bisect
        blamef = "blame --first-parent";
        bisectf = "bisect start --first-parent";

        # Branch cleanup
        cleanup = "!git branch --merged | grep -v '\\*\\|master\\|main' | xargs -n 1 git branch -d";

        # Interactive rebase helper
        tidy = "rebase -i @{upstream}";

        # Force merge commit
        mergeff = "merge --no-ff";
      };

      init.defaultBranch = "master";

      # Merge settings
      merge = {
        conflictStyle = "zdiff3"; # Better than diff3, shows common ancestor
        ff = false; # Always create merge commits to preserve branch structure
      };

      # Diff settings
      diff = {
        colorMoved = "default";
        algorithm = "histogram"; # Better diff algorithm
      };

      # Pull/fetch behavior
      pull.rebase = true; # Rebase local commits when pulling
      fetch.prune = true; # Auto-prune deleted remote branches

      # Rebase settings
      rebase = {
        autoStash = true; # Automatically stash/unstash when rebasing
        autoSquash = true; # Automatically mark fixup! commits during interactive rebase
      };

      # Push settings
      push.autoSetupRemote = true; # Automatically set up remote tracking on first push

      # Branch settings
      branch.autoSetupMerge = "always"; # Always set up tracking when creating branches

      # Rerere (reuse recorded resolution)
      rerere.enabled = true; # Remember how conflicts were resolved

      delta = {
        "line-numbers" = true;
        "side-by-side" = false;
        navigate = true;
      };

      difftool.prompt = false;
      "difftool \"difftastic\"" = {
        cmd = ''difft --display=inline --background=dark --width="$(tput cols)" "$LOCAL" "$REMOTE"'';
      };

      "credential \"https://github.com\"".helper = githubHelper;
      "credential \"https://api.github.com\"".helper = githubHelper;
    };
  };

  programs.delta = {
    enable = true;
    enableGitIntegration = true;
  };
}
