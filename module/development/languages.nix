# Development Languages and Tools
# Programming languages, language servers, formatters, linters, and development tools

{
  pkgs,
  inputs,
  ...
}:
{
  config = {
    home-manager.users.sinity = {
      home = {
        packages = with pkgs; [
          # Language Servers, Formatters, Linters
          markdown-oxide # Used by obsidian.nvim
          nixfmt-rfc-style # Preferred Nix formatter
          nixd
          nil
          nix-diff

          # Rust development
          rustup
          cargo-fuzz
          cargo-bump
          cargo-audit

          # JavaScript/Node.js
          nodejs

          # Python with packages bundled
          (python3.withPackages (
            ps: with ps; [
              pip
              ipython
              rich
              click
              questionary
              fuzzywuzzy
              fastapi
              uvicorn
              aiofiles
              pydantic
              python-Levenshtein
              ujson
              tiktoken
              # Add commonly used packages
              pandas
              numpy
              requests
              matplotlib
              seaborn
              jupyter
              notebook
              black
              mypy
              pytest
              httpx
              beautifulsoup4
              lxml
              python-dotenv
              tqdm
              typer
              pyyaml
              toml
              tabulate
            ]
          ))

          # Database tools
          sqlite
          sqlitebrowser
          sqlite-vec
          sqlite-utils
          sqlitestudio
          pgcli
          # postgresql_16

          # AI development tools
          aider-chat # aider-chat-full # Temporarily disabled due to spacy dependency issues
          claude-code
          inputs.claude-squad.packages.${pkgs.system}.default # Manage multiple AI coding assistants
          codex
          openai-whisper-cpp

          # Git tools
          gh # GitHub CLI
          delta
          lazygit # TUI for git
          onefetch # Git repo stats
          gitui
          
        ];
      };

      # VS Code configuration
      programs.vscode = {
        enable = true;
        extensions = with pkgs.vscode-extensions; [
          # Essential development extensions
          ms-python.python
          
          # Rust development
          rust-lang.rust-analyzer
          
          # Nix development
          bbenoist.nix
          
          # Git integration
          eamodio.gitlens
          
          # Theme and UI
          dracula-theme.theme-dracula
          pkief.material-icon-theme
          
          # Markdown
          yzhang.markdown-all-in-one
          
          # Neovim integration
          asvetliakov.vscode-neovim
        ];
        userSettings = {
          # Theme and appearance (let stylix handle fonts and themes)
          "workbench.iconTheme" = "material-icon-theme";
          "window.menuBarVisibility" = "toggle";
          "editor.fontLigatures" = true;
          
          # Editor behavior
          "editor.formatOnSave" = true;
          "editor.formatOnPaste" = true;
          "editor.tabSize" = 2;
          "editor.insertSpaces" = true;
          "editor.rulers" = [ 80 120 ];
          "editor.minimap.enabled" = false;
          "editor.lineNumbers" = "on";
          "editor.renderWhitespace" = "boundary";
          "editor.wordWrap" = "bounded";
          "editor.wordWrapColumn" = 120;
          
          # File management
          "files.autoSave" = "afterDelay";
          "files.autoSaveDelay" = 1000;
          "files.trimTrailingWhitespace" = true;
          "files.insertFinalNewline" = true;
          "files.trimFinalNewlines" = true;
          
          # Git integration
          "git.autofetch" = true;
          "git.enableSmartCommit" = true;
          "gitlens.codeLens.enabled" = true;
          
          # Language-specific settings
          "rust-analyzer.checkOnSave.command" = "check";
          "rust-analyzer.cargo.loadOutDirsFromCheck" = true;
          "python.defaultInterpreterPath" = "/run/current-system/sw/bin/python3";
          "nix.enableLanguageServer" = true;
          "nix.serverPath" = "nixd";
          
          # Neovim integration settings
          "vscode-neovim.neovimExecutablePaths.linux" = "/run/current-system/sw/bin/nvim";
          "vscode-neovim.neovimInitVimPaths.linux" = "/home/sinity/.config/nvim/init.lua";
          "vscode-neovim.useWSL" = false;
          
          
          # Other productivity settings
          "explorer.confirmDelete" = false;
          "explorer.confirmDragAndDrop" = false;
          "workbench.startupEditor" = "none";
          "extensions.autoUpdate" = false;
          "telemetry.telemetryLevel" = "off";
        };
        
        keybindings = [];
      };
    };
  };
}
