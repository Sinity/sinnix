let
  exportSecret = name: path: ''
    export ${name}="$(<${path})"
  '';
in
  {
    config,
    pkgs,
    lib,
    ...
  }: {
    imports = [];

    # Define environment variables that use the decrypted secrets
    programs.zsh.loginShellInit = lib.concatLines [
      (exportSecret "OPENAI_API_KEY" config.age.secrets.openai-api-key.path)
      (exportSecret "OBSIDIAN_REST_API_KEY" config.age.secrets.obsidian-api-key.path)
      (exportSecret "GEMINI_API_KEY" config.age.secrets.gemini-api-key.path)
      (exportSecret "ANTHROPIC_API_KEY" config.age.secrets.anthropic-api-key.path)
      (exportSecret "RAINDROP_TOKEN" config.age.secrets.raindrop-token.path)
      (exportSecret "ASSEMBLYAI_API_KEY" config.age.secrets.assemblyai-api-key.path)
      (exportSecret "FACTORIO_TOKEN" config.age.secrets.factorio-token.path)
      (exportSecret "GITHUB_TOKEN" config.age.secrets.github-token.path)
      (exportSecret "NIX_GITHUB_TOKEN" config.age.secrets.github-token.path)
    ];

    # Add decryption configuration
    age = {
      identityPaths = ["/home/sinity/.ssh/id_ed25519"];

      secrets = {
        # API keys
        openai-api-key = {
          file = ../../secrets/openai-api-key.age;
          owner = "sinity";
        };

        obsidian-api-key = {
          file = ../../secrets/obsidian-api-key.age;
          owner = "sinity";
        };

        gemini-api-key = {
          file = ../../secrets/gemini-api-key.age;
          owner = "sinity";
        };

        anthropic-api-key = {
          file = ../../secrets/anthropic-api-key.age;
          owner = "sinity";
        };

        assemblyai-api-key = {
          file = ../../secrets/assemblyai-api-key.age;
          owner = "sinity";
        };

        raindrop-token = {
          file = ../../secrets/raindrop-token.age;
          owner = "sinity";
        };

        factorio-token = {
          file = ../../secrets/factorio-token.age;
          owner = "sinity";
        };

        github-token = {
          file = ../../secrets/github-token.age;
          owner = "sinity";
        };
      };
    };
  }
