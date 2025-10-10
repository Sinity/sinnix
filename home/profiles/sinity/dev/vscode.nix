{ pkgs, ... }:
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
          pkgs.nix-vscode-extensions.vscode-marketplace.rlivings39.fzf-quick-open
          pkgs.nix-vscode-extensions.vscode-marketplace.mkhl.direnv
          pkgs.nix-vscode-extensions.vscode-marketplace.vspacecode.whichkey
          pkgs.vscode-extensions.eamodio.gitlens
          pkgs.nix-vscode-extensions.vscode-marketplace.usernamehw.errorlens
          pkgs.nix-vscode-extensions.vscode-marketplace.foam.foam-vscode
          pkgs.nix-vscode-extensions.vscode-marketplace.yzhang.markdown-all-in-one
          pkgs.nix-vscode-extensions.vscode-marketplace.streetsidesoftware.code-spell-checker
          pkgs.nix-vscode-extensions.vscode-marketplace.serayuzgur.crates
        ];
    };
  };
}
