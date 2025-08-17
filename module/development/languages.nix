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
              gitpython  # For git analysis tools
              # Data visualization and analysis
              plotly
              bokeh
              altair
              pygal
              holoviews
              # Time series analysis
              statsmodels
              # Git analysis
              # pydriller  # Git repository mining (not in nixpkgs)
              # Diagram generation
              diagrams  # Diagram as code
              graphviz  # Graph visualization
              pydot  # Graphviz interface
              networkx  # Network analysis
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

      # VS Code - installed but not configured by Nix
      programs.vscode = {
        enable = true;
        # Extensions and settings are now managed manually in ~/.config/Code/User/
        # To restore configuration:
        # 1. Extensions: code --install-extension <extension-id>
        # 2. Settings: copy to ~/.config/Code/User/settings.json
        # 3. Keybindings: copy to ~/.config/Code/User/keybindings.json
      };
    };
  };
}
