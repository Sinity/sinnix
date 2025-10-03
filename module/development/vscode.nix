{ pkgs, ... }:
{
  programs.vscode = {
    enable = true;

    # Only manage extensions; do not manage user settings or keybindings
    profiles.default = {
      extensions =
        (with pkgs.vscode-extensions; [
          # UI & Theme
          enkia.tokyo-night
          vscode-icons-team.vscode-icons
          oderwat.indent-rainbow

          # Language Support
          jnoortheen.nix-ide
          rust-lang.rust-analyzer
          ms-python.python
          ms-python.vscode-pylance
          tamasfe.even-better-toml

          # Vim Emulation
          asvetliakov.vscode-neovim
          # Standards & Conventions
          editorconfig.editorconfig
        ])
        ++ [
          # Marketplace extensions
          pkgs.nix-vscode-extensions.vscode-marketplace.rlivings39.fzf-quick-open
          pkgs.nix-vscode-extensions.vscode-marketplace.mkhl.direnv

          # WhichKey UI for leader key menus (matches your settings.json bindings)
          pkgs.nix-vscode-extensions.vscode-marketplace.vspacecode.whichkey

          # Git ergonomics and inline diagnostics
          pkgs.nix-vscode-extensions.vscode-marketplace.eamodio.gitlens
          pkgs.nix-vscode-extensions.vscode-marketplace.usernamehw.errorlens

          # Markdown/Notes and spell checking
          pkgs.nix-vscode-extensions.vscode-marketplace.foam.foam-vscode
          pkgs.nix-vscode-extensions.vscode-marketplace.yzhang.markdown-all-in-one
          pkgs.nix-vscode-extensions.vscode-marketplace.streetsidesoftware.code-spell-checker

          # Rust quality-of-life
          pkgs.nix-vscode-extensions.vscode-marketplace.serayuzgur.crates
        ];

      # Intentionally do not set userSettings or keybindings here to avoid
      # clobbering repo-managed dotfiles in ~/.config/Code/User.
    };
  };
}
