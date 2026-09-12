# Optional GPU media-generation toolchain. The durable model and application
# state remains in place when this profile is disabled.
{ config, lib, ... }:
let
  cfg = config.sinnix.profiles.ai-media;
in
{
  options.sinnix.profiles.ai-media.enable = lib.mkEnableOption "local AI media-generation services";

  config = {
    sinnix.services = {
      comfyui.enable = lib.mkDefault cfg.enable;
      tts.enable = lib.mkDefault cfg.enable;
      musicgen.enable = lib.mkDefault cfg.enable;
      ocr.enable = lib.mkDefault cfg.enable;
    };
  };
}
