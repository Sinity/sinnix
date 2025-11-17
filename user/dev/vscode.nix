{
  pkgs,
  inputs,
  dotsPath,
  lib,
  config,
  ...
}:
let
  pkgsWithMarketplace = pkgs.extend inputs.nix-vscode-extensions.overlays.default;
  marketplace = pkgsWithMarketplace.nix-vscode-extensions.vscode-marketplace;
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
          marketplace.foam.foam-vscode
          marketplace.yzhang.markdown-all-in-one
          marketplace.streetsidesoftware.code-spell-checker
          marketplace.serayuzgur.crates
          marketplace."sst-dev".opencode
          marketplace.xiangz19.codex-ratelimit
        ];
    };
  };

  xdg.configFile = {
    "Code/User/settings.json".source = dotsPath + "/vscode/User/settings.json";
    "Code/User/keybindings.json".source = dotsPath + "/vscode/User/keybindings.json";
    "Code/User/mcp.json".text = lib.replaceStrings [ "/home/sinity" ] [ config.home.homeDirectory ] (
      builtins.readFile (dotsPath + "/vscode/User/mcp.json")
    );
    "Code/User/mcp" = {
      source = dotsPath + "/vscode/User/mcp";
      recursive = true;
      force = true;
    };
  };

  stylix.targets.vscode.enable = false;
}
