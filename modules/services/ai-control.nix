# sinnix-ai — on-demand control plane for the local AI services
# (whisper, tts, ollama, litellm, llama-cpp, koboldcpp, comfyui, musicgen,
# ocr, open-webui). The script carries the service registry; this module
# only installs it. See scripts/sinnix-ai.
{ pkgs, helpers, ... }:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
{
  environment.systemPackages = [ scriptPkgs.sinnix-ai ];
}
