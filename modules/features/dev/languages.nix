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
      aiTools = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system};

      # Pin claude-code ahead of upstream llm-agents when it lags behind.
      # To update: nix-prefetch-url the new binary URL, convert to SRI hash.
      # Remove this override once llm-agents catches up.
      claude-code = aiTools.claude-code.overrideAttrs (old: rec {
        version = "2.1.111";
        src = pkgs.fetchurl {
          url = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/${version}/linux-x64/claude";
          hash = "sha256-XU35cAQLD4OqxDSuVAtAkSakd4o3noybTHk1YOO/oGA=";
        };
      });
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
          claude-code
          aiTools.codex
          aiTools.forge
        ];
      })
    ];
} args
