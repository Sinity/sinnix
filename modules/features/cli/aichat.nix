# aichat — terminal client wired to the local Ollama hub (OpenAI-compatible).
{
  mkFeatureModule,
  pkgs,
  lib,
  helpers,
  ...
}@args:
let
  chatModel =
    lib.findSingle (model: model.litellmName == "local-chat")
      (throw "aichat requires a local-chat model")
      (throw "aichat local-chat model is ambiguous")
      helpers.data.localModels.models;
in
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
        model: ollama:${chatModel.ollamaTag}
        clients:
          - type: openai-compatible
            name: ollama
            api_base: ${helpers.data.localModels.ollamaApiBase}/v1
      '';
    };
} args
