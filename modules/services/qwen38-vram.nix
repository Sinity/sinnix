# Qwen3.8 27B abliterated-family fully-VRAM-resident llama.cpp endpoint.
#
# Ollama cannot pin per-model load options, and its silent layer-spill turns
# this dense 27B into a 1.2 tok/s crawl the moment the estimate misses (the
# CPU-resident layers gate every token; measured 2026-08-31, vs 40.7 tok/s
# fully resident). This endpoint owns the exact fit instead: strict full
# offload with a small compute batch and bounded context, sized so the
# UD-IQ2_XXS build sits entirely in the 3080's VRAM beside the desktop's
# ~1.5 GB. A load failure under an unusually heavy desktop is deliberate:
# fail loudly rather than degrade into the split.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkServiceModule {
  name = "qwen38-vram";
  description = "Qwen3.8 27B VRAM-resident llama.cpp inference";
  docs = "docs/local-ai-activation.md";
  surface = {
    unit = "qwen38-vram.service";
    resourceClass = "interactive-agent";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:${toString helpers.data.ports.qwen38Vram.public}";
      backendEndpoint = "127.0.0.1:${toString helpers.data.ports.qwen38Vram.backend}";
      idleTimeout = "900s";
      readinessTimeout = 600;
      exclusiveResource = "gpu-inference";
      dependsOn = [ "qwen38-vram-proxy" ];
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    model = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "Qwen3.8 GGUF filename under model/gguf to load at start.";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      modelRoot = "${config.sinnix.paths.modelsRoot}";
      args' = lib.escapeShellArgs [
        "${pkgs.llama-cpp-cuda}/bin/llama-server"
        "--model"
        "${modelRoot}/gguf/${cfg.model}"
        "--host"
        "127.0.0.1"
        "--port"
        (toString helpers.data.ports.qwen38Vram.backend)
        # Strict residency: every layer on the GPU or the load fails.
        # Batch 64 keeps the compute buffer small enough to clear the fit
        # (batch 512 alone pushed the total past free VRAM). With the KV
        # cache quantized to q8_0 under flash attention, the hybrid-attention
        # cache costs ~32 KB/token: 16K ctx loads with ~1 GB of VRAM slack
        # (measured 2026-08-31; 32K also loads but leaves only ~400 MB,
        # one Chrome spike from eviction — not the default).
        "--n-gpu-layers"
        "999"
        "--ctx-size"
        "16384"
        "--batch-size"
        "64"
        "--ubatch-size"
        "64"
        "--parallel"
        "1"
        "--flash-attn"
        "on"
        "--cache-type-k"
        "q8_0"
        "--cache-type-v"
        "q8_0"
        "--no-mmproj"
        # Qwen3.8 ships its own chat template; without --jinja the model
        # loses turn boundaries and rambles past stop tokens.
        "--jinja"
      ];
    in
    {
      systemd.tmpfiles.rules = [
        "d ${modelRoot}/gguf 0755 ${user} users -"
      ];

      systemd.services.qwen38-vram = {
        description = "Qwen3.8 27B VRAM-resident llama.cpp server";
        wantedBy = [ ];
        after = [ "network.target" ];
        partOf = [ "qwen38-vram-proxy.service" ];
        serviceConfig = lib.mkMerge [
          {
            User = user;
            Group = "users";
            SupplementaryGroups = [
              "video"
              "render"
            ];
            ExecStart = args';
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "qwen38-vram.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 30;
          })
        ];
      };
    };
} args
