# llama.cpp HTTP server — raw GGUF endpoint for experiments and for applying
# steering / abliteration control vectors via --control-vector.
#
# Enabled on sinnix-prime (hosts/sinnix-prime/default.nix) serving a 0.6B
# reranker (/v1/rerank — an API ollama does not provide); koboldcpp remains
# the everyday vehicle for general LLM/VLM chat. The host pins gpuLayers = 0:
# measured 2026-08-13 the reranker answers in 435-571ms on pure CPU versus
# 67-137ms on GPU, so it runs CPU-only and outside the gpu-inference
# admission mesh — it can sit resident alongside ollama, koboldcpp, or any
# other CUDA backend instead of evicting/being evicted by one. It does NOT
# hold zero VRAM, though: the CUDA-linked binary still allocates
# ~680-740MiB even with --n-gpu-layers 0 (verified live, released cleanly
# on exit) -- far below the 1610MiB it held fully offloaded, but a real
# cost worth remembering when reasoning about coexistence headroom on a
# 10GB card. `package = pkgs.llama-cpp-cuda` below stays as-is: the CUDA
# build runs on CPU with `-ngl 0` without a separate rebuild; a future GGUF
# served through this module with gpuLayers > 0 would need to opt back into
# the mesh. If the ~700MiB CUDA-context floor ever becomes a problem, a
# genuinely CUDA-free build would remove it entirely -- not attempted here.
# Socket-activated behind
# the same idle-aware proxy pattern as ollama/koboldcpp/whisper
# (modules/services/ai-control.nix): the public port 8081 is the systemd
# socket front door, the backend runs on a private loopback port and exits
# after idle. DynamicUser + ProtectSystem=strict is read-only, not hidden, so
# it reads the model under /realm without extra bind mounts.
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
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:8081";
      backendEndpoint = "127.0.0.1:8082";
      # Measured 2026-08-13: ~1-3s cold /v1/rerank round trip for the 0.6B
      # reranker -- 30s is already ~10-30x headroom, kept unchanged.
      idleTimeout = "30s";
      dependsOn = [ "llama-cpp-proxy" ];
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
    ctxSize = args.lib.mkOption {
      type = args.lib.types.int;
      default = 4096;
      description = ''
        `--ctx-size` (KV-cache context window, tokens). Left unset upstream
        this loads the model's full training context, which is what
        inflated the reranker's VRAM footprint to ~5.6 GB idle; a reranker
        only ever sees one query/document pair at a time, so a modest bound
        is enough headroom without paying for context it never uses.
      '';
    };
    extraFlags = args.lib.mkOption {
      type = args.lib.types.attrsOf args.lib.types.anything;
      default = { };
      description = "Extra llama-server settings merged verbatim (e.g. { reranking = true; }).";
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
          # 8081 is reserved for the socket-activated front door
          # (llama-cpp-proxy). Keep the daemon on a private loopback port so
          # clients cannot bypass lifecycle admission and idle teardown.
          port = 8082;
          flash-attn = "on";
          n-gpu-layers = cfg.gpuLayers;
          ctx-size = cfg.ctxSize;
        }
        // lib.optionalAttrs (cfg.model != "") {
          model = "${modelRoot}/gguf/${cfg.model}";
        }
        // lib.optionalAttrs (cfg.controlVector != "") {
          control-vector = "${modelRoot}/control-vectors/${cfg.controlVector}";
        }
        // cfg.extraFlags;
      };

      systemd.services.llama-cpp = {
        # On-demand, socket-activated via llama-cpp-proxy — never resident
        # at boot, never holds VRAM while idle.
        wantedBy = lib.mkForce [ ];
        partOf = [ "llama-cpp-proxy.service" ];
        bindsTo = [ "llama-cpp-proxy.service" ];
        # CPU-pinned (gpuLayers = 0, set on the host): deliberately NOT in
        # ai-control.nix's gpuInferenceConflicts mesh, so it can run
        # alongside a resident ollama/koboldcpp/whisper session instead of
        # evicting/being evicted by one.
      };
    };
} args
