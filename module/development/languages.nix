# Development Languages and Tools
# Programming languages, language servers, formatters, linters, and development tools

{
  pkgs,
  config,
  inputs,
  ...
}:
{
  config = {
    home-manager.users.sinity = {
      imports = [ ./vscode.nix ];

      home = {
        packages = with pkgs; [
          # Language Servers, Formatters, Linters
          markdown-oxide # Used by obsidian.nvim
          nixfmt-rfc-style # Preferred Nix formatter
          nixd
          nil
          nix-diff

          # Rust Development
          rustup
          cargo-fuzz
          cargo-bump
          cargo-audit

          # Web Development
          nodejs

          # Python Development
          (python3.withPackages (ps: with ps; [
            # Core
            pip
            ipython
            # CLI & TUI
            rich
            click
            questionary
            typer
            tqdm
            # Web & API
            fastapi
            uvicorn
            aiofiles
            httpx
            beautifulsoup4
            requests
            # Data Science & ML
            pandas
            numpy
            matplotlib
            seaborn
            jupyter
            notebook
            plotly
            bokeh
            altair
            pygal
            holoviews
            statsmodels
            # Data Formats
            pydantic
            pyyaml
            toml
            ujson
            # Tooling
            black
            mypy
            pytest
            python-dotenv
            # Misc
            fuzzywuzzy
            python-Levenshtein
            tiktoken
            tabulate
            gitpython # For git analysis tools
            # Diagramming
            diagrams
            graphviz
            pydot
            networkx
          ]))

          # Database Tools
          sqlite
          sqlitebrowser
          sqlite-vec
          sqlite-utils
          sqlitestudio
          pgcli

          # AI Development
          aider-chat
          claude-code
          inputs.claude-squad.packages.${pkgs.system}.default
          codex
          openai-whisper-cpp

          # Git Tools
          gh
          delta
          lazygit
          onefetch
          gitui

          # Fonts
          jetbrains-mono
        ];
      };
    };
  };
}
