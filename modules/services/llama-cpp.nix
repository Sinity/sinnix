# llama.cpp HTTP server — raw GGUF endpoint for experiments and for applying
# steering / abliteration control vectors via --control-vector.
#
# On sinnix-prime this serves a 0.6B reranker (/v1/rerank — an API ollama
# does not provide) with gpuLayers = 0, which keeps it CPU-only and outside
# ai-control.nix's gpu-inference admission mesh, so it can sit resident
# alongside ollama or koboldcpp. The package FOLLOWS gpuLayers (see below);
# a future GGUF served here with gpuLayers > 0 gets the CUDA build
# automatically and would need to opt back into the exclusivity mesh.
#
# Socket-activated behind the same idle-aware proxy pattern as
# ollama/koboldcpp/muse-glimmer (modules/services/ai-control.nix): port 8081 is
# the systemd socket front door, the backend runs on a private loopback port
# and exits after idle. DynamicUser + ProtectSystem=strict is read-only, not
# hidden, so it reads the model under /realm without extra bind mounts.
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
      default = 0;
      description = ''
        `--ctx-size` (KV-cache context window, tokens). 0 means the
        model's own trained context -- llama-server's own default, and the
        right one here: cropping a reranker's context silently truncates
        long documents and scores only their head.

        llama.cpp allocates the KV cache up front for whatever this is set
        to; it does not grow on demand. That is affordable only because
        gpuLayers = 0 puts the cache in system RAM rather than the 10 GB
        card. Raise gpuLayers and this bound starts costing VRAM again.
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
      modelRoot = "${config.sinnix.paths.modelsRoot}";
    in
    {
      services.llama-cpp = {
        enable = true;
        # The package must follow gpuLayers rather than being pinned to CUDA:
        # a CUDA-linked binary allocates its context and compute buffers at
        # build/link time, not per offload setting, so it still holds
        # ~700 MiB of VRAM at --n-gpu-layers 0. On a 10 GB card that erases
        # the headroom this service exists to preserve. At gpuLayers = 0 CUDA
        # has nothing to do, so the CPU build is the same computation
        # without the context.
        package = if cfg.gpuLayers == 0 then pkgs.llama-cpp else pkgs.llama-cpp-cuda;
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
      };
    };
} args
