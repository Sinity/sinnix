{ pkgs, inputs, ... }:
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
        ];
    };
  };
}
