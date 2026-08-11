# Ollama — local LLM/VLM inference hub (OpenAI-compatible API on 127.0.0.1:11434).
#
# This is the Tier-1 daily driver: Open WebUI and aichat both target it. Weights
# live on durable /realm (NOT the wear-limited root SSD); CUDA via the prebuilt
# `ollama-cuda`. Automatic VRAM<->RAM offload handles models that don't fully fit
# the 3080's 10 GB.
#
# DynamicUser note: the upstream unit sets DynamicUser=true *and* User=. When
# User= names an existing static account, systemd uses that account, which is
# what lets the daemon write the /realm models dir. We point it at the human
# user so the dir it owns (created via tmpfiles below) is writable.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "ollama";
  description = "Ollama local LLM/VLM inference hub (CUDA)";
  surface = {
    unit = "ollama.service";
    resourceClass = "interactive-agent"; # uncapped memory — required for RAM offload
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:11434";
      backendEndpoint = "127.0.0.1:11435";
      idleTimeout = "30s";
      exclusiveResource = "gpu-inference";
      dependsOn = [ "ollama-proxy" ];
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = true;
      description = "Start Ollama automatically at boot.";
    };
    loadModels = args.lib.mkOption {
      type = args.lib.types.listOf args.lib.types.str;
      default = [
        # Edit to taste; a failed pull only fails the loader oneshot, not
        # the system.
        # Uncensored chat tier: Gemma 4 12B abliterated (current gen, dense,
        # VRAM-resident). Replaces the 2024-era llama3.2-abliterate 3B.
        "huihui_ai/gemma-4-abliterated:12b"
        # Vision + general multimodal tier: Gemma 4 12B QAT (7.2 GB, dense,
        # fully VRAM-resident, text+image+audio in, 128K ctx). Replaces
        # llava, which it outclasses across the board.
        "gemma4:12b-it-qat"
        # Embeddings for Open WebUI RAG / document chat. qwen3-embedding
        # 0.6b: 70.7 MTEB-eng-v2 vs nomic-embed-text's ~62 at 1.2 GB.
        # Existing RAG collections re-embed on next use.
        "qwen3-embedding:0.6b"
        # Coding, GPU-resident tier: dense 7B coder fits the 3080's 10 GB at
        # Q4 with room for KV cache. Triage/dedup/format-verdict grade.
        "qwen2.5-coder:7b"
        # Coding, stretch tier: 30B MoE with only ~3B active params (19 GB
        # Q4). Ollama splits GPU/CPU automatically; the active-expert
        # working set keeps token rates usable despite not fitting VRAM.
        "qwen3-coder:30b"
        # General reasoning/agentic MoE (~3.6B active, native MXFP4, 14 GB).
        # Same partial-offload story as qwen3-coder.
        "gpt-oss:20b"
        # General MoE with hybrid thinking mode (~3B active, 19 GB Q4) —
        # reasoning-heavy non-code tasks.
        "qwen3:30b"
        # Multimodal MoE (18 GB, 256K ctx, Arena 1441) — the strongest
        # local generalist this host can run via partial offload.
        "gemma4:26b"
        # Experimental embedding pulls (HF GGUF, community/official builds) —
        # kept LAST so an unsupported-architecture pull failure cannot block
        # the core roster above. Verify each actually loads before relying
        # on it (novel embedder archs can outrun ollama's llama.cpp vintage).
        # Jina v5 text-small retrieval-tuned (official GGUF; ~71.7 MTEB v2
        # class at 677M).
        "hf.co/jinaai/jina-embeddings-v5-text-small-retrieval-GGUF"
        # Microsoft Harrier-OSS v1 0.6b (MIT; the family's headline 74.3
        # multilingual score is the 27b — this small one will land lower).
        "hf.co/SuperPauly/harrier-oss-v1-0.6b-gguf"
        # Voyage 4 nano — the open-weight member of the Voyage 4 shared
        # embedding space (community GGUF).
        "hf.co/jsonMartin/voyage-4-nano-gguf"
        # ReaderLM-v2: Jina's open 1.5B HTML->markdown/JSON converter
        # (beats GPT-4o-class on that niche; 512K combined tokens).
        "hf.co/rbehzadan/ReaderLM-v2.gguf"
      ];
      description = "Models pre-pulled by the ollama-model-loader oneshot.";
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
      user = config.sinnix.user.name;
      modelsDir = "${config.sinnix.paths.mediaRoot}/model/ollama";
    in
    {
      services.ollama = {
        enable = true;
        package = pkgs.ollama-cuda;
        # Dedicated static system user (created by the module). systemd uses the
        # static account over DynamicUser, so it can own/write the /realm models
        # dir. Reusing the human user would rewrite their home dir → HM conflict.
        user = "ollama";
        group = "ollama";
        host = "127.0.0.1";
        # 11434 is reserved for the socket-activated front door. Keep the
        # daemon on a private loopback port so clients cannot bypass lifecycle
        # admission and idle teardown.
        port = 11435;
        openFirewall = false;
        inherit modelsDir;
        inherit (cfg) loadModels;
        environmentVariables = {
          OLLAMA_FLASH_ATTENTION = "1";
          OLLAMA_KEEP_ALIVE = "30m";
          # 10 GB VRAM: keep one model resident at a time to avoid thrashing.
          OLLAMA_MAX_LOADED_MODELS = "1";
        };
      };

      # /realm is durable (separate fs, outside impermanence) — only create+own
      # the tree; no sinnix.persistence declaration needed.
      systemd.tmpfiles.rules = [
        # Shared parent owned by the human user; ollama subdir owned by the
        # ollama service account (0755 keeps the parent traversable).
        "d ${config.sinnix.paths.mediaRoot}/model 0755 ${user} users -"
        "d ${modelsDir} 0755 ollama ollama -"
      ];

      environment.systemPackages = [ pkgs.ollama-cuda ]; # `ollama` CLI on PATH

      systemd.services = lib.mkMerge [
        (lib.mkIf (!cfg.autoStart) {
          ollama.wantedBy = lib.mkForce [ ];
          ollama-model-loader.wantedBy = lib.mkForce [ ];
        })
        {
          ollama.partOf = [ "ollama-proxy.service" ];
          ollama.bindsTo = [ "ollama-proxy.service" ];
          ollama.conflicts = [
            "koboldcpp.service"
            "koboldcpp-proxy.service"
          ];
          # The loader must pull through the FRONT door: pulls against the
          # private backend port are invisible to the socket-proxy's idle
          # timer, so 30s into a multi-GB download the proxy idle-exits and
          # takes ollama (bindsTo) and the loader down with it — observed
          # 2026-08-11: loader killed at 2min with 0 bytes landed. Front-door
          # traffic holds the proxy connection open for the whole pull.
          ollama-model-loader.environment.OLLAMA_HOST = lib.mkForce "127.0.0.1:11434";
        }
      ];
    };
} args
