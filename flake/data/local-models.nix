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
      ollamaTag = "hf.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF:Q4_K_M";
      litellmName = "local-gemma4-26b-abliterated";
      role = "uncensored-multimodal-moe";
      expectedBytes = null;
      notes = ''
        Abliterated Gemma 4 26B-A4B Q4_K_M GGUF (about 16.8 GB), the
        refusal-removed counterpart to gemma4:26b. It is a MoE model with
        about 4B active parameters per token and uses Ollama's HF GGUF
        importer.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3.8-abliterated:27b";
      litellmName = "local-qwen38";
      role = "uncensored-flagship-offload";
      expectedBytes = null;
      notes = ''
        Qwen3.8 27B abliterated (huihui; 2026-08 release, 28B dense,
        hybrid attention, 262K native ctx) — the flagship general tier,
        ~17 GB Q4-class with partial RAM offload like qwen3-coder:30b.
        Hybrid attention caches only 16 of 64 layers (~64 KB/token), so
        long contexts stay affordable despite the dense parameter count.
        The official qwen3.8:27b tag needs a newer client than ollama
        0.32.7 (registry answers 412); huihui's upload carries no such
        gate and pulled cleanly (verified 2026-08-31).
      '';
    }
    {
      ollamaTag = null;
      litellmName = "local-qwen38-vram";
      role = "general-flagship-vram";
      expectedBytes = null;
      litellmModel = "openai/qwen38-vram";
      litellmApiBase = "http://127.0.0.1:8085/v1";
      litellmApiKey = "sk-local";
      notes = ''
        Qwen3.8 27B UD-IQ2_XXS on the dedicated qwen38-vram llama.cpp
        endpoint (modules/services/qwen38-vram.nix), which owns the exact
        fit: strict full offload, batch 64, ctx 4096. Measured 2026-08-31:
        40.7 tok/s fully resident vs 1.2 tok/s when ollama silently spilled
        16% of layers to CPU — ollama cannot pin per-model load options,
        which is why this tier is not an ollama tag. Text-only (no mmproj);
        larger quants (UD-IQ2_S 8.42 GB abliterated included) exceed the
        ~8.7 GB the desktop leaves free once compute buffers are counted.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:4b-instruct";
      litellmName = "local-qwen3-vl-abliterated-4b";
      role = "uncensored-vlm-bulk";
      expectedBytes = null;
      notes = ''
        Qwen3-VL abliterated 4B (3.3 GB, dense) — bulk frame-captioning
        tier for library-scale passes where per-image cost dominates.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:8b-instruct";
      litellmName = "local-qwen3-vl-abliterated-8b";
      role = "uncensored-vlm";
      expectedBytes = null;
      notes = ''
        Qwen3-VL abliterated 8B instruct (6.1 GB, dense, fully
        VRAM-resident) — the default uncensored vision lane. Instruct, not
        thinking: the thinking tags spend max_tokens on reasoning and
        return empty content for bulk caption calls. Supplants stashbox's private
        llama.cpp/koboldcpp endpoint on :8899 and the JoyCaption GGUFs;
        stashbox consumes this through LiteLLM (bead stashbox-1mx).
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct";
      litellmName = "local-qwen3-vl-abliterated-30b";
      role = "uncensored-vlm-moe";
      expectedBytes = null;
      notes = ''
        Qwen3-VL abliterated 30B-A3B (20 GB, MoE, ~3B active) — quality
        tier via partial RAM offload, same fit story as qwen3-coder:30b.
      '';
    }
    {
      ollamaTag = null;
      litellmName = "local-glimmer";
      role = "general-reasoning-hybrid-dense";
      expectedBytes = null;
      litellmModel = "openai/muse-glimmer";
      litellmApiBase = "http://127.0.0.1:8083/v1";
      litellmApiKey = "sk-local";
      notes = ''
        Abliterated Muse Glimmer 30B Q4_K_M deployment (about 16.9 GB), served
        by the dedicated llama.cpp endpoint. Its fit policy places as many
        layers as possible on the RTX 3080 and keeps the remainder in system
        RAM. Reasoning tier for local agent jobs and batch work; use
        local-glimmer through LiteLLM.
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
    "local-qwen38"
    "local-qwen38-vram"
    "local-glimmer"
    "local-reader"
    "local-multimodal-moe"
    "local-gemma4-26b-abliterated"
    "local-qwen3-vl-abliterated-4b"
    "local-qwen3-vl-abliterated-8b"
    "local-qwen3-vl-abliterated-30b"
  ];

  byLitellmName = lib.listToAttrs (
    map (m: lib.nameValuePair m.litellmName m) (lib.filter (m: m.litellmName != null) models)
  );
in
rec {
  inherit models ollamaApiBase;

  # modules/services/ollama.nix `loadModels` default: plain ordered tag list.
  ollamaLoadModels = map (m: m.ollamaTag) (lib.filter (m: m.ollamaTag != null) models);

  # modules/services/litellm.nix `settings.model_list`.
  litellmModelList = map (
    name:
    let
      m = byLitellmName.${name};
    in
    {
      model_name = name;
      litellm_params = {
        model = if m ? litellmModel then m.litellmModel else "ollama_chat/${m.ollamaTag}";
        api_base = if m ? litellmApiBase then m.litellmApiBase else ollamaApiBase;
      }
      // lib.optionalAttrs (m ? litellmApiKey) {
        api_key = m.litellmApiKey;
      };
    }
  ) litellmOrder;

  # modules/services/open-webui.nix `RAG_EMBEDDING_MODEL`.
  ragEmbeddingOllamaTag = (lib.findFirst (m: m.role == "rag-embedding") null models).ollamaTag;

  # Sideloaded GGUF files under /realm/library/models/gguf (not pulled through
  # ollama). Consumed by modules/services/llama-cpp.nix's reranker endpoint;
  # hosts/sinnix-prime picks the active one via `llama-cpp.model`. Data only
  # today — no fetch/verify machinery reads this list yet.
  ggufSideloads = [
    {
      file = "Qwen3.8-27B-UD-IQ2_XXS.gguf";
      url = "https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-IQ2_XXS.gguf";
      # Hardlinked from the ollama blob store (same bytes ollama pulled);
      # size from stat on disk.
      expectedBytes = 7266070528;
    }
    {
      file = "qwen3-reranker-0.6b-q8_0.gguf";
      url = "https://huggingface.co/dean2155/Qwen3-Reranker-0.6B-Q8_0-GGUF/resolve/main/qwen3-reranker-0.6b-q8_0.gguf";
      # Authoritative size from the HF tree API.
      expectedBytes = 639150304;
    }
    {
      # Higher-quality manual swap-in for the 0.6b default above. Not
      # currently on disk under /realm/library/models/gguf — re-populate
      # expectedBytes if it is re-sideloaded.
      file = "Qwen.Qwen3-Reranker-4B.Q4_K_M.gguf";
      url = "https://huggingface.co/DevQuasar/Qwen.Qwen3-Reranker-4B-GGUF/resolve/main/Qwen.Qwen3-Reranker-4B.Q4_K_M.gguf";
      expectedBytes = null; # populate from the completed download
    }
    {
      file = "muse-glimmer-30B-kquant-17gb.gguf";
      url = "https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF/resolve/main/muse-glimmer-30B-kquant-17gb.gguf";
      expectedBytes = 16756681056;
    }
    {
      file = "Muse-Glimmer-30B-Abliterated-Q4_K_M.gguf";
      url = "https://huggingface.co/Blackfrost-AI/Muse-Glimmer-30B-Abliterated-GGUF/resolve/main/Muse-Glimmer-30B-Abliterated-Q4_K_M.gguf";
      expectedBytes = 16935296896;
    }
  ];
}
