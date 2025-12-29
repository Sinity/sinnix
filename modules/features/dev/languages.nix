{
  pkgs,
  inputs,
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix.features.dev.languages;
  user = config.sinnix.user.name;
in
{
  options.sinnix.features.dev.languages = {
    enable = lib.mkEnableOption "Programming Language Toolchains";
  };

  config = lib.mkIf cfg.enable {
    home-manager.users.${user} = { pkgs, inputs, ... }: {
      home.packages =
        let
          aiToolsBase = inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system};
          aiTools = aiToolsBase;
          externalTools = [
            inputs.sinevec.packages.${pkgs.stdenv.hostPlatform.system}.sinevec
          ];
        in
        (with pkgs; [
          markdown-oxide
          nixfmt-rfc-style
          nixd
          nil
          nix-diff
          rustup
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
              marimo
              litellm
              openai
              anthropic
              google-genai
              mcp
              qdrant-client
            ]
          ))
          sqlite
          sqlite-vec
          sqlite-utils
          sqlitestudio
          pgcli
          aider-chat
          whisper-cpp
          gh
          delta
          lazygit
          onefetch
          gitui
          jetbrains-mono
        ])
        ++ externalTools
        ++ [
          aiTools.claude-code
          aiTools.opencode
          pkgs.codex
        ];
    };
  };
}