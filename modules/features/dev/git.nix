{ mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [ "dev" "git" ];
  description = "Git and delta tooling";
  configFn =
    { config, lib, user, ... }:
    let
      githubTokenPath = config.sinnix.secrets.paths."github-token";
      githubHelper = ''!f(){ if [ -r ${githubTokenPath} ]; then token="$(tr -d '\r\n' < ${githubTokenPath})"; printf 'username=x-access-token\npassword=%s\n' "$token"; fi; }; f'';
    in
    {
      home-manager.users.${user} = { ... }: {
        programs.git = {
          enable = true;
          signing = {
            key = "0x5E6A3B1F";
            signByDefault = false;
          };
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
              lg = "log --first-parent --oneline --decorate";
              lgg = "log --first-parent --graph --oneline --decorate";
              lga = "log --graph --oneline --decorate --all";
              lgf = "log --graph --oneline --decorate";
              review = "log --first-parent --graph --oneline --decorate @{upstream}..HEAD";
              incoming = "log --first-parent --oneline --decorate ..@{upstream}";
              outgoing = "log --first-parent --oneline --decorate @{upstream}..";
              blamef = "blame --first-parent";
              bisectf = "bisect start --first-parent";
              cleanup = "!git branch --merged | grep -v '\\*\\|master\\|main' | xargs -n 1 git branch -d";
              tidy = "rebase -i @{upstream}";
              mergeff = "merge --no-ff";
            };
            init.defaultBranch = "master";
            core.editor = "nvim";
            merge = {
              conflictStyle = "zdiff3";
              ff = false;
            };
            color = {
              ui = "auto";
              branch = "auto";
              diff = "auto";
              interactive = "auto";
              status = "auto";
            };
            diff = {
              colorMoved = "default";
              algorithm = "histogram";
            };
            pull.rebase = true;
            fetch.prune = true;
            rebase = {
              autoStash = true;
              autoSquash = true;
            };
            push.autoSetupRemote = true;
            branch.autoSetupMerge = "always";
            rerere.enabled = true;
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
      };
    };
} args
