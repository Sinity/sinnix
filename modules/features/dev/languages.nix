{ mkFeatureModule, inputs, pkgs, ... }@args:
mkFeatureModule {
  path = [ "dev" "languages" ];
  description = "Programming language toolchains";
  configFn =
    { config, pkgs, inputs, ... }:
    let
      user = config.sinnix.user.name;
      aiTools = inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system};
    in
    {
      home-manager.users.${user} = { pkgs, inputs, ... }: {
        home.packages = with pkgs; [
          nixfmt-rfc-style
          nil
          nix-diff
          rustup
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
              tabulate
              httpx
              requests
              beautifulsoup4
              fastapi
              uvicorn
              pydantic
              pydantic-settings
              python-dotenv
              pyyaml
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
            ]
          ))
          sqlite
          sqlite-vec
          pgcli
          aider-chat
          whisper-cpp
          gh
          delta
          jetbrains-mono
          aiTools.claude-code
          aiTools.opencode
          codex
        ];
      };
    };
} args
