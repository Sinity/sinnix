# llama.cpp HTTP server (CUDA) — raw GGUF endpoint for experiments and for
# applying steering / abliteration control vectors via --control-vector.
#
# Opt-in (disabled by default in the host); koboldcpp already bundles llama.cpp
# for everyday use. Enable this when you want a clean llama-server with explicit
# sampling/control-vector flags. DynamicUser + ProtectSystem=strict is read-only,
# not hidden, so it reads the model under /realm without extra bind mounts.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "llama-cpp";
  description = "llama.cpp HTTP server (CUDA)";
  surface = {
    unit = "llama-cpp.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    model = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "GGUF filename under model/gguf to serve (required when enabled).";
    };
    gpuLayers = args.lib.mkOption {
      type = args.lib.types.int;
      default = 999;
      description = "Layers offloaded to GPU; remainder runs on CPU/RAM.";
    };
    controlVector = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "Control-vector GGUF filename under model/control-vectors to apply (empty = none).";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      ...
    }:
    let
      modelRoot = "${config.sinnix.paths.mediaRoot}/model";
    in
    {
      services.llama-cpp = {
        enable = true;
        package = pkgs.llama-cpp-cuda;
        settings = {
          host = "127.0.0.1";
          port = 8081;
          flash-attn = "on";
          n-gpu-layers = cfg.gpuLayers;
        }
        // lib.optionalAttrs (cfg.model != "") {
          model = "${modelRoot}/gguf/${cfg.model}";
        }
        // lib.optionalAttrs (cfg.controlVector != "") {
          control-vector = "${modelRoot}/control-vectors/${cfg.controlVector}";
        };
      };
    };
} args
