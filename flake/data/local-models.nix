# Local model roster — single source shared by three consumers:
# modules/services/ollama.nix (loadModels), modules/services/litellm.nix
# (settings.model_list), and modules/services/open-webui.nix
# (RAG_EMBEDDING_MODEL). Edit the roster here; the consumer modules only
# render it.
{ lib }:
let
  # Loopback endpoint every local-model consumer targets.
  ollamaApiBase = "http://127.0.0.1:11434";

  # Canonical roster, in ollama-pull order (the order modules/services/
  # ollama.nix pre-pulls them at boot via the ollama-model-loader oneshot).
  # litellmName is null for models never exposed through the LiteLLM
  # Anthropic/OpenAI gateway — the RAG/embedding models are consumed
  # directly by Ollama/Open WebUI instead.
  models = [
    {
      ollamaTag = "huihui_ai/gemma-4-abliterated:12b";
      litellmName = "local-chat";
      role = "uncensored-chat";
      expectedBytes = null;
      notes = ''
        Uncensored chat tier: Gemma 4 12B abliterated (current gen, dense,
        VRAM-resident). Replaces the 2024-era llama3.2-abliterate 3B.
      '';
    }
    {
      ollamaTag = "gemma4:12b-it-qat";
      litellmName = "local-vision";
      role = "vision-multimodal";
      expectedBytes = null;
      notes = ''
        Vision + general multimodal tier: Gemma 4 12B QAT (7.2 GB, dense,
        fully VRAM-resident, text+image+audio in, 128K ctx). Replaces llava,
        which it outclasses across the board.
      '';
    }
    {
      ollamaTag = "qwen3-embedding:0.6b";
      litellmName = null;
      role = "rag-embedding";
      expectedBytes = null;
      notes = ''
        Embeddings for Open WebUI RAG / document chat. qwen3-embedding 0.6b:
        70.7 MTEB-eng-v2 vs nomic-embed-text's ~62 at 1.2 GB. Existing RAG
        collections re-embed on next use.
      '';
    }
    {
      ollamaTag = "qwen2.5-coder:7b";
      litellmName = "local-coder";
      role = "coding-gpu-resident";
      expectedBytes = null;
      notes = ''
        Coding, GPU-resident tier: dense 7B coder fits the 3080's 10 GB at Q4
        with room for KV cache. Triage/dedup/format-verdict grade.
      '';
    }
    {
      ollamaTag = "qwen3-coder:30b";
      litellmName = "local-coder-moe";
      role = "coding-moe-stretch";
      expectedBytes = null;
      notes = ''
        Coding, stretch tier: 30B MoE with only ~3B active params (19 GB Q4).
        Ollama splits GPU/CPU automatically; the active-expert working set
        keeps token rates usable despite not fitting VRAM.
      '';
    }
    {
      ollamaTag = "gpt-oss:20b";
      litellmName = "local-reasoner";
      role = "general-reasoning-moe";
      expectedBytes = null;
      notes = ''
        General reasoning/agentic MoE (~3.6B active, native MXFP4, 14 GB).
        Same partial-offload story as qwen3-coder.
      '';
    }
    {
      ollamaTag = "qwen3:30b";
      litellmName = "local-thinker";
      role = "general-reasoning-hybrid-thinking";
      expectedBytes = null;
      notes = ''
        General MoE with hybrid thinking mode (~3B active, 19 GB Q4) —
        reasoning-heavy non-code tasks.
      '';
    }
    {
      ollamaTag = "gemma4:26b";
      litellmName = "local-multimodal-moe";
      role = "multimodal-moe-generalist";
      expectedBytes = null;
      notes = ''
        Multimodal MoE (18 GB, 256K ctx, Arena 1441) — the strongest local
        generalist this host can run via partial offload.
      '';
    }
    {
      ollamaTag = "muse-glimmer";
      litellmName = "local-glimmer";
      role = "general-reasoning-hybrid-dense";
      expectedBytes = null;
      notes = ''
        Official Muse Glimmer 30B Q4 deployment (about 17 GB). Ollama's CUDA
        backend splits the dense model between RTX 3080 VRAM and system RAM.
        Reasoning tier for local agent jobs and batch work; use local-glimmer
        through LiteLLM.
      '';
    }
    # Experimental embedding pulls (HF GGUF, community/official builds) —
    # kept LAST in the ollama pull order so an unsupported-architecture pull
    # failure cannot block the core roster above. Verify each actually loads
    # before relying on it (novel embedder archs can outrun ollama's
    # llama.cpp vintage).
    {
      ollamaTag = "hf.co/jinaai/jina-embeddings-v5-text-small-retrieval-GGUF";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Jina v5 text-small retrieval-tuned (official GGUF; ~71.7 MTEB v2
        class at 677M).
      '';
    }
    {
      ollamaTag = "hf.co/SuperPauly/harrier-oss-v1-0.6b-gguf";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Microsoft Harrier-OSS v1 0.6b (MIT; the family's headline 74.3
        multilingual score is the 27b — this small one will land lower).
      '';
    }
    {
      ollamaTag = "hf.co/jsonMartin/voyage-4-nano-gguf";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Voyage 4 nano — the open-weight member of the Voyage 4 shared
        embedding space (community GGUF).
      '';
    }
    {
      ollamaTag = "hf.co/rbehzadan/ReaderLM-v2.gguf";
      litellmName = "local-reader";
      role = "html-to-markdown-reader";
      expectedBytes = null;
      notes = ''
        ReaderLM-v2: Jina's open 1.5B HTML->markdown/JSON converter (beats
        GPT-4o-class on that niche; 512K combined tokens).
      '';
    }
  ];

  # LiteLLM exposes chat/coding/reasoning models in a different order from
  # the ollama pull roster above (RAG/embedding models are never listed —
  # they have no litellmName).
  litellmOrder = [
    "local-chat"
    "local-vision"
    "local-coder"
    "local-coder-moe"
    "local-reasoner"
    "local-thinker"
    "local-glimmer"
    "local-reader"
    "local-multimodal-moe"
  ];

  byLitellmName = lib.listToAttrs (
    map (m: lib.nameValuePair m.litellmName m) (lib.filter (m: m.litellmName != null) models)
  );
in
rec {
  inherit models ollamaApiBase;

  # modules/services/ollama.nix `loadModels` default: plain ordered tag list.
  ollamaLoadModels = map (m: m.ollamaTag) models;

  # modules/services/litellm.nix `settings.model_list`.
  litellmModelList = map (
    name:
    let
      m = byLitellmName.${name};
    in
    {
      model_name = name;
      litellm_params = {
        model = "ollama_chat/${m.ollamaTag}";
        api_base = ollamaApiBase;
      };
    }
  ) litellmOrder;

  # modules/services/open-webui.nix `RAG_EMBEDDING_MODEL`.
  ragEmbeddingOllamaTag = (lib.findFirst (m: m.role == "rag-embedding") null models).ollamaTag;

  # Sideloaded GGUF files under /realm/media/model/gguf (not pulled through
  # ollama). Consumed by modules/services/llama-cpp.nix's reranker endpoint;
  # hosts/sinnix-prime picks the active one via `llama-cpp.model`. Data only
  # today — no fetch/verify machinery reads this list yet.
  ggufSideloads = [
    {
      file = "qwen3-reranker-0.6b-q8_0.gguf";
      url = "https://huggingface.co/dean2155/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf";
      # Authoritative size from the HF tree API.
      expectedBytes = 639150304;
    }
    {
      # Higher-quality manual swap-in for the 0.6b default above. Not
      # currently on disk under /realm/media/model/gguf — re-populate
      # expectedBytes if it is re-sideloaded.
      file = "Qwen.Qwen3-Reranker-4B.Q4_K_M.gguf";
      url = "https://huggingface.co/DevQuasar/Qwen.Qwen3-Reranker-4B-GGUF/resolve/main/Qwen.Qwen3-Reranker-4B.Q4_K_M.gguf";
      expectedBytes = null; # populate from the completed download
    }
  ];
}
