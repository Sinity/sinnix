{
  config,
  pkgs,
  lib,
  ...
}: {
  imports = [];

  # Define environment variables that use the decrypted secrets
  environment.sessionVariables = {
    OPENAI_API_KEY = "$(cat ${config.age.secrets.openai-api-key.path})";
    OBSIDIAN_REST_API_KEY = "$(cat ${config.age.secrets.obsidian-api-key.path})";
    GEMINI_API_KEY = "$(cat ${config.age.secrets.gemini-api-key.path})";
    ANTHROPIC_API_KEY = "$(cat ${config.age.secrets.anthropic-api-key.path})";
    RAINDROP_TOKEN = "$(cat ${config.age.secrets.raindrop-token.path})";
    ASSEMBLYAI_API_KEY = "$(cat ${config.age.secrets.assemblyai-api-key.path})";
    FACTORIO_TOKEN = "$(cat ${config.age.secrets.factorio-token.path})";
  };

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
    };
  };
}
