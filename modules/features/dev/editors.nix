{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.editors;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.editors = {
    vscode.enable = lib.mkEnableOption "VSCode Editor";
    zed.enable = lib.mkEnableOption "Zed Editor";
  };

  config = lib.mkMerge [
    (lib.mkIf cfg.vscode.enable {
      home-manager.users.${user} =
        {
          pkgs,
          helpers,
          lib,
          config,
          dotsRepoPath,
          ...
        }:
        let
          marketplace = pkgs.nix-vscode-extensions.vscode-marketplace;
          mkDotsRepoLink = helpers.mkDotsSymlink config dotsRepoPath;
        in
        {
          programs.vscode = {
            enable = true;
            profiles.default = {
              extensions =
                (with pkgs.vscode-extensions; [
                  enkia.tokyo-night
                  vscode-icons-team.vscode-icons
                  oderwat.indent-rainbow
                  jnoortheen.nix-ide
                  rust-lang.rust-analyzer
                  ms-python.python
                  ms-python.vscode-pylance
                  tamasfe.even-better-toml
                  asvetliakov.vscode-neovim
                  editorconfig.editorconfig
                ])
                ++ [
                  marketplace.rlivings39.fzf-quick-open
                  marketplace.mkhl.direnv
                  marketplace.vspacecode.whichkey
                  pkgs.vscode-extensions.eamodio.gitlens
                  marketplace.usernamehw.errorlens
                  marketplace.yzhang.markdown-all-in-one
                  marketplace."sst-dev".opencode
                  marketplace.xiangz19.codex-ratelimit
                ];
            };
          };

          xdg.configFile = {
            "Code/User/settings.json".source = mkDotsRepoLink "/vscode/User/settings.json";
            "Code/User/keybindings.json".source = mkDotsRepoLink "/vscode/User/keybindings.json";
            "Code/User/mcp.json".source = mkDotsRepoLink "/vscode/User/mcp.json";
            "Code/User/mcp" = {
              source = mkDotsRepoLink "/vscode/User/mcp";
              force = true;
            };
          };

          home.activation.cleanupVscodeMcp = lib.hm.dag.entryBefore [ "linkGeneration" ] ''
            rm -rf "$HOME/.config/Code/User/mcp"
          '';

          stylix.targets.vscode.enable = false;
        };
    })

    (lib.mkIf cfg.zed.enable {
      home-manager.users.${user} =
        {
          config,
          dotsRepoPath,
          helpers,
          ...
        }:
        let
          mkDotsRepoLink = helpers.mkDotsSymlink config dotsRepoPath;
        in
        {
          xdg.configFile = {
            # Zed uses lowercase 'zed' for its config directory
            "zed/settings.json".source = mkDotsRepoLink "/zed/settings.json";
            "zed/keymap.json".source = mkDotsRepoLink "/zed/keymap.json";
          };

          home.file.".local/bin/zed" = {
            text = ''
              #!/usr/bin/env bash
              set -euo pipefail
              exec zeditor "$@"
            '';
            executable = true;
          };
        };
    })
  ];
}
