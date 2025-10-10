{ pkgs, inputs, ... }:
{
  imports = [ ./vscode.nix ];

  home.packages = with pkgs; [
    markdown-oxide
    nixfmt-rfc-style
    nixd
    nil
    nix-diff
    rustup
    cargo-fuzz
    cargo-bump
    cargo-audit
    nodejs
    (python3.withPackages (
      ps: with ps; [
        pip
        ipython
        rich
        click
        questionary
        typer
        tqdm
        fastapi
        uvicorn
        aiofiles
        httpx
        beautifulsoup4
        requests
        pydantic
        pydantic-settings
        python-dotenv
        pyyaml
        toml
        ujson
        tabulate
        tiktoken
        gitpython
        black
        mypy
        pytest
      ]
    ))
    sqlite
    sqlitebrowser
    sqlite-vec
    sqlite-utils
    sqlitestudio
    pgcli
    aider-chat
    claude-code
    inputs.claude-squad.packages.${pkgs.system}.default
    codex
    openai-whisper-cpp
    gh
    delta
    lazygit
    onefetch
    gitui
    jetbrains-mono
  ];
}
