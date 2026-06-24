# aichat — terminal client wired to the local Ollama hub (OpenAI-compatible).
{
  mkFeatureModule,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "aichat"
  ];
  description = "aichat CLI wired to local Ollama";
  configFn =
    {
      pkgs,
      user,
      ...
    }:
    {
      environment.systemPackages = [ pkgs.aichat ];

      home-manager.users.${user}.xdg.configFile."aichat/config.yaml".text = ''
        model: ollama:huihui_ai/llama3.2-abliterate
        clients:
          - type: openai-compatible
            name: ollama
            api_base: http://127.0.0.1:11434/v1
      '';
    };
} args
