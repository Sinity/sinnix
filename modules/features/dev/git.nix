{
  pkgs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.git;
  user = config.sinnix.user.name;
  githubHelper = pkgs.writeShellScript "gh-auth-helper" ''
    exec ${lib.getExe pkgs.gh} auth git-credential "$@"
  '';
in
{
  options.sinnix.features.dev.git = {
    enable = lib.mkEnableOption "Git and related tools";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} =
      { pkgs, lib, ... }:
      {
        programs.git = {
          enable = true;
          userName = "Sinity";
          userEmail = "sinity@sinnix.dev";

          # Signing settings
          signing = {
            key = "0x5E6A3B1F";
            signByDefault = false;
          };

          aliases = {
            co = "checkout";
            ci = "commit";
            st = "status";
            br = "branch";
            hist = "log --pretty=format:'%h %ad | %s%d [%an]' --graph --date=short";
            type = "cat-file -t";
            dump = "cat-file -p";
          };

          extraConfig = {
            init.defaultBranch = "master";
            pull.rebase = true;

            # Core settings
            core = {
              editor = "nvim";
            };

            # Color settings
            color = {
              ui = "auto";
              branch = "auto";
              diff = "auto";
              interactive = "auto";
              status = "auto";
            };

            # Rebase settings
            rebase = {
              autoStash = true;
              autoSquash = true;
            };

            # Push settings
            push.autoSetupRemote = true;

            # Branch settings
            branch.autoSetupMerge = "always";

            # Rerere
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

            "credential \"https://github.com\"".helper = "${githubHelper}";
            "credential \"https://api.github.com\"".helper = "${githubHelper}";
          };
        };

        programs.delta = {
          enable = true;
          enableGitIntegration = true;
        };
      };
  };
}
