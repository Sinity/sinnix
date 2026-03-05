{
  mkFeatureModule,
  inputs,
  pkgs,
  lib,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "languages"
  ];
  description = "Programming language toolchains";
  subFeatures = {
    nix = {
      description = "Nix language tooling (nixfmt, nil, nix-diff)";
      default = true;
    };
    python = {
      description = "Python 3 with common packages";
      default = true;
    };
    nodejs = {
      description = "Node.js runtime";
      default = true;
    };
    database = {
      description = "Database clients (sqlite, pgcli)";
      default = true;
    };
    ai = {
      default = true;
    };
  };
  configFn =
    {
      config,
      pkgs,
      lib,
      inputs,
      cfg,
      user,
      ...
    }:
    let
      aiTools = inputs.nix-ai-tools.packages.${pkgs.stdenv.hostPlatform.system};
    in
    lib.mkMerge [
      # Nix tooling
      (lib.mkIf cfg.nix.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          nixfmt
          nil
          nix-diff
        ];
      })

      # Python with common packages
      (lib.mkIf cfg.python.enable {
        home-manager.users.${user}.home.packages = [
          (pkgs.python3.withPackages (
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
              llm
              openai
              anthropic
              google-genai
            ]
          ))
        ];
      })

      # Node.js
      (lib.mkIf cfg.nodejs.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          nodejs
        ];
      })

      # Database tools
      (lib.mkIf cfg.database.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          sqlite
          sqlite-vec
          pgcli
        ];
      })

      # AI coding tools
      (lib.mkIf cfg.ai.enable {
        home-manager.users.${user}.home.packages = [
          pkgs.whisper-cpp
          pkgs.gh
          pkgs.delta
          pkgs.jetbrains-mono
          aiTools.claude-code
          aiTools.codex
        ];
      })
    ];
} args
