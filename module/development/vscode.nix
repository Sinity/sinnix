{
  pkgs,
  lib,
  config,
  ...}:
let
  # Helper function to generate keybindings for vscode-neovim
  mkSendKey = key: {
    inherit key;
    command = "vscode-neovim.send";
    args = key;
    when = "editorTextFocus && neovim.mode != 'insert'";
  };
  mkCtrlSendKey = key: {
    key = "ctrl+${key}";
    command = "vscode-neovim.send";
    args = "<C-${key}>";
    when = "editorTextFocus && neovim.mode != 'insert'";
  };

  # Lists of keys to forward
  letters = [ "a" "b" "c" "d" "e" "f" "g" "h" "i" "j" "k" "l" "m" "n" "o" "p" "q" "r" "s" "t" "u" "v" "w" "x" "y" "z" ];
  upperCaseLetters = [ "A" "B" "C" "D" "E" "F" "G" "H" "I" "J" "K" "L" "M" "N" "O" "P" "Q" "R" "S" "T" "U" "V" "W" "X" "Y" "Z" ];
  numbers = [ "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" ];
  symbols = [ "-" "=" "[" "]" "\"" ";" "'" "," "." "/" "`" "!" "@" "#" "$" "%" "^" "&" "*" "(" ")" ];
  ctrlKeys = [ "[" "]" "f" "b" "d" "u" "w" "h" "j" "k" "l" ];
  specialKeys = [
    { key = "space"; command = "vscode-neovim.send"; args = " "; when = "editorTextFocus && neovim.mode != 'insert'"; }
  ];
in
{
  programs.vscode = {
    enable = true;

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
          pkgs.nix-vscode-extensions.vscode-marketplace.rlivings39.fzf-quick-open
          pkgs.nix-vscode-extensions.vscode-marketplace.zaidalsaheb.search-preview
        ];

      userSettings = {
        # Theme & Font
        "workbench.iconTheme" = "vscode-icons";
        "workbench.colorTheme" = "Tokyo Night";
        "editor.fontFamily" = "JetBrains Mono";
        "editor.fontLigatures" = true;
        "editor.fontSize" = 14;

        # Advanced Styling
        "editor.bracketPairColorization.enabled" = true;
        "editor.guides.bracketPairs" = "active";
        "editor.guides.indentation" = true;
        "editor.guides.highlightActiveIndentation" = true;

        # Editor Control
        "files.autoSave" = "onFocusChange";
        "editor.smoothScrolling" = true;
        "editor.linkedEditing" = true;
        "editor.formatOnPaste" = true;
        "editor.codeActionsOnSave" = {
          "source.fixAll" = true;
          "source.organizeImports" = true;
        };

        # UI Layout
        "workbench.activityBar.visible" = false;
        "breadcrumbs.enabled" = true;
        "editor.renderWhitespace" = "selection";
        "editor.renderControlCharacters" = true;
        "workbench.editor.labelFormat" = "medium";

        # Terminal & Git
        "terminal.integrated.fontFamily" = "JetBrains Mono";
        "git.autofetch" = true;
        "git.confirmSync" = false;

        # Nix Language Server
        "nix.enable" = true;
        "nix.serverPath" = "nixd";
        "nix.formatterPath" = "nixfmt-rfc-style";

        # NeoVim Extension
        "vscode-neovim.neovimInitVimPaths.linux" = "${config.home.homeDirectory}/.config/nvim/init.lua";
      };

      keybindings = lib.concatLists [
        (lib.map mkSendKey letters)
        (lib.map mkSendKey upperCaseLetters)
        (lib.map mkSendKey numbers)
        (lib.map mkSendKey symbols)
        (lib.map mkCtrlSendKey ctrlKeys)
        specialKeys
      ];
    };
  };
}
