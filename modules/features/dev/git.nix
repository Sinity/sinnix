{ mkFeatureModule, ... }@args:
mkFeatureModule {
  path = [
    "dev"
    "git"
  ];
  description = "Git and delta tooling";
  configFn =
    {
      config,
      lib,
      user,
      ...
    }:
    let
      secretsEnabled = config.sinnix.secrets.enable;
      githubTokenPath =
        if secretsEnabled then config.sinnix.secrets.paths."github-token" else "/dev/null";
      githubHelper = ''!f(){ if [ -r ${githubTokenPath} ]; then token="$(tr -d '\r\n' < ${githubTokenPath})"; printf 'username=x-access-token\npassword=%s\n' "$token"; fi; }; f'';
    in
    {
      home-manager.users.${user} = _: {
        programs.git = {
          enable = true;
          signing = {
            format = "ssh";
            key = "/home/sinity/.ssh/id_ed25519_github.pub";
            signByDefault = true;
          };
          settings = {
            user = {
              name = "Sinity";
              email = "ezo.dev@gmail.com";
            };
            gpg.ssh.allowedSignersFile = "~/.config/git/allowed_signers";
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
              cleanup = "!~/.local/bin/git-cleanup-merged-pr-branches";
              tidy = "rebase -i @{upstream}";
              mergeff = "merge --no-ff";
            };
            init.defaultBranch = "master";
            core.editor = "nvim";
            core.excludesFile = "~/.config/git/ignore_global";
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

        home.file.".config/git/ignore_global".text = ''
          AGENTS.md
        '';

        home.file.".local/bin/git-cleanup-merged-pr-branches" = {
          executable = true;
          text = ''
            #!/usr/bin/env bash
            set -euo pipefail

            if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
              echo "not inside a git worktree" >&2
              exit 1
            fi

            current="$(git branch --show-current 2>/dev/null || true)"
            origin_head="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
            default_branch="''${origin_head#origin/}"
            if [ -z "$default_branch" ] || [ "$default_branch" = "$origin_head" ]; then
              default_branch="master"
            fi

            base="origin/$default_branch"
            if ! git rev-parse --verify --quiet "$base" >/dev/null; then
              if git rev-parse --verify --quiet origin/main >/dev/null; then
                base="origin/main"
              elif git rev-parse --verify --quiet origin/master >/dev/null; then
                base="origin/master"
              else
                base="HEAD"
              fi
            fi

            is_protected_branch() {
              local branch="$1"
              if [ -z "$branch" ] || [ "$branch" = "$current" ]; then
                return 0
              fi

              case "$branch" in
                master|main|develop|dev|trunk)
                  return 0
                  ;;
                *)
                  return 1
                  ;;
              esac
            }

            git fetch --prune --quiet || echo "warning: fetch --prune failed; continuing with local branch metadata" >&2

            git branch --format='%(refname:short)' --merged "$base" |
              while IFS= read -r branch; do
                if is_protected_branch "$branch"; then
                  continue
                fi
                git branch -d "$branch"
              done

            if ! command -v gh >/dev/null 2>&1; then
              echo "gh not found; skipped gone-upstream squash-merge cleanup" >&2
              exit 0
            fi

            git for-each-ref --format='%(refname:short)%09%(upstream:track)' refs/heads |
              awk -F '\t' '$2 == "[gone]" { print $1 }' |
              while IFS= read -r branch; do
                if is_protected_branch "$branch"; then
                  continue
                fi

                pr_number="$(
                  gh pr list \
                    --state merged \
                    --head "$branch" \
                    --json number \
                    --jq '.[0].number // empty' 2>/dev/null || true
                )"

                if [ -n "$pr_number" ]; then
                  echo "Deleting $branch; merged PR #$pr_number"
                  git branch -D "$branch"
                else
                  echo "Keeping $branch; upstream is gone but no merged GitHub PR was found" >&2
                fi
              done
          '';
        };

        home.file.".config/git/allowed_signers".text = ''
          ezo.dev@gmail.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBn+iIA903PeKrQvEmJl3Q8kE1haD6HkSZCoXEp6sFFR
        '';

        programs.delta = {
          enable = true;
          enableGitIntegration = true;
        };

        programs.lazygit.enable = true;
      };
    };
} args
