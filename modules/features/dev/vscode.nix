{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.vscode;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.vscode = {
    enable = lib.mkEnableOption "VSCode Editor";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, dotsRepoPath, lib, config, ... }:
      let
        marketplace = pkgs.nix-vscode-extensions.vscode-marketplace;
        mkDotsRepoLink = rel: config.lib.file.mkOutOfStoreSymlink (dotsRepoPath + rel);
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
  };
}
