{config, pkgs, lib, ...}:

{
  imports = [ ];

  # Define environment variables that use the decrypted secrets
  environment.sessionVariables = {
    OPENAI_API_KEY = "$(cat ${config.age.secrets.openai-api-key.path})";
    OBSIDIAN_REST_API_KEY = "$(cat ${config.age.secrets.obsidian-api-key.path})";
  };
  
  # Add decryption configuration
  age = {
    identityPaths = [ "/home/sinity/.ssh/id_ed25519" ];
    
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
      
      # SSH keys
      ssh-id-ed25519 = {
        file = ../../secrets/ssh-id-ed25519.age;
        path = "/home/sinity/.ssh/id_ed25519";
        owner = "sinity";
        mode = "0600";
      };
      
      ssh-id-ed25519-github = {
        file = ../../secrets/ssh-id-ed25519-github.age;
        path = "/home/sinity/.ssh/id_ed25519_github";
        owner = "sinity";
        mode = "0600";
      };
    };
  };
}