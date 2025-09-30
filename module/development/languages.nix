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
          # Lean Python toolchain; project-specific data-science stacks can be
          # layered with `uv`/virtualenvs on demand.
          (python3.withPackages (
            ps: with ps; [
              # Core tooling
              pip
              ipython
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
              pydantic
              pydantic-settings
              python-dotenv
              # Data formats & utilities
              pyyaml
              toml
              ujson
              tabulate
              tiktoken
              gitpython
              # Quality
              black
              mypy
              pytest
            ]
          ))

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
