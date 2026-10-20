# Local model roster. Ollama renders pull tags, LiteLLM renders routes,
# Open WebUI selects embeddings, and aichat selects the default chat model.
# Model names, fit arguments, and notes belong here; consumers render them.
{ lib }:
let
  # Loopback endpoint every local-model consumer targets.
  ollamaApiBase = "http://127.0.0.1:11434";

  # Ollama pull order. A null litellmName keeps a model out of the chat
  # gateway; embedding consumers use Ollama directly.
  models = [
    {
      ollamaTag = "huihui_ai/gemma-4-abliterated:12b";
      litellmName = "local-chat";
      role = "uncensored-chat";
      expectedBytes = null;
      notes = ''
        Gemma 4 12B abliterated, dense and VRAM-resident, for text chat.
      '';
    }
    {
      ollamaTag = "gemma4:12b-it-qat";
      litellmName = "local-vision";
      role = "vision-multimodal";
      expectedBytes = null;
      notes = ''
        Gemma 4 12B QAT: dense, VRAM-resident text, image, and audio input.
      '';
    }
    {
      ollamaTag = "qwen3-embedding:0.6b";
      litellmName = null;
      role = "rag-embedding";
      expectedBytes = null;
      notes = ''
        Open WebUI document embeddings. Changing the embedding model
        requires re-embedding existing collections.
      '';
    }
    {
      ollamaTag = "qwen2.5-coder:7b";
      litellmName = "local-coder";
      role = "coding-gpu-resident";
      expectedBytes = null;
      notes = ''
        Dense 7B coding model at Q4, sized for the RTX 3080 with KV cache.
      '';
    }
    {
      ollamaTag = "qwen3-coder:30b";
      litellmName = "local-coder-moe";
      role = "coding-moe-stretch";
      expectedBytes = null;
      notes = ''
        30B MoE coding model, about 3B active parameters and 19 GB at Q4.
        Ollama splits weights across GPU and system RAM.
      '';
    }
    {
      ollamaTag = "gpt-oss:20b";
      litellmName = "local-reasoner";
      role = "general-reasoning-moe";
      expectedBytes = null;
      notes = ''
        General reasoning MoE, about 3.6B active parameters and 14 GB in
        MXFP4. Requires partial offload to system RAM.
      '';
    }
    {
      ollamaTag = "qwen3:30b";
      litellmName = "local-thinker";
      role = "general-reasoning-hybrid-thinking";
      expectedBytes = null;
      notes = ''
        General reasoning MoE with hybrid thinking mode, about 3B active
        parameters and 19 GB at Q4.
      '';
    }
    {
      ollamaTag = "gemma4:26b";
      litellmName = "local-multimodal-moe";
      role = "multimodal-moe-generalist";
      expectedBytes = null;
      notes = ''
        Multimodal MoE, about 18 GB, served with partial RAM offload.
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
        Dense Qwen3.8 27B abliterated, about 17 GB with partial RAM offload.
        This community tag avoids the official tag's client-version gate.
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
        Text-only Qwen3.8 27B UD-IQ2_XXS through the dedicated llama.cpp
        profile below. Explicit full offload, batch, context, and KV settings
        avoid Ollama's automatic CPU spill. Larger quants need additional
        VRAM for compute buffers beyond their weight size.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:4b-instruct";
      litellmName = "local-qwen3-vl-abliterated-4b";
      role = "uncensored-vlm-bulk";
      expectedBytes = null;
      notes = ''
        Dense Qwen3-VL abliterated 4B, about 3.3 GB, for bulk captioning.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:8b-instruct";
      litellmName = "local-qwen3-vl-abliterated-8b";
      role = "uncensored-vlm";
      expectedBytes = null;
      notes = ''
        Dense Qwen3-VL abliterated 8B instruct, about 6.1 GB and
        VRAM-resident, for vision through LiteLLM. Instruct avoids thinking
        variants spending the caption token budget before visible output.
      '';
    }
    {
      ollamaTag = "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct";
      litellmName = "local-qwen3-vl-abliterated-30b";
      role = "uncensored-vlm-moe";
      expectedBytes = null;
      notes = ''
        Qwen3-VL abliterated 30B-A3B, about 20 GB with 3B active
        parameters, for vision with partial RAM offload.
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
    # Experimental embeddings and the reader follow core pulls so an
    # unsupported architecture cannot block them. Verify model load before use.
    {
      ollamaTag = "hf.co/jinaai/jina-embeddings-v5-text-small-retrieval-GGUF";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Jina v5 text-small retrieval embeddings, official GGUF.
      '';
    }
    {
      ollamaTag = "hf.co/SuperPauly/harrier-oss-v1-0.6b-gguf";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Microsoft Harrier-OSS v1 0.6B embeddings, community GGUF.
      '';
    }
    {
      ollamaTag = "hf.co/jsonMartin/voyage-4-nano-gguf";
      litellmName = null;
      role = "experimental-embedding";
      expectedBytes = null;
      notes = ''
        Voyage 4 nano embeddings, community GGUF.
      '';
    }
    {
      ollamaTag = "hf.co/rbehzadan/ReaderLM-v2.gguf";
      litellmName = "local-reader";
      role = "html-to-markdown-reader";
      expectedBytes = null;
      notes = ''
        ReaderLM-v2, Jina's 1.5B HTML to Markdown or JSON converter.
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

  # Named llama.cpp services share one renderer and activation lifecycle.
  llamaCppProfiles = {
    llama-cpp = {
      description = "llama.cpp reranker";
      portKey = "llamaCpp";
      model = "qwen3-reranker-0.6b-q8_0.gguf";
      requiresCuda = false;
      dynamicUser = true;
      idleTimeout = "30s";
      readinessTimeout = 30;
      arguments = [
        "--ctx-size"
        "0"
        "--flash-attn"
        "on"
        "--n-gpu-layers"
        "0"
        "--reranking"
      ];
    };
    qwen38-vram = {
      description = "Qwen3.8 27B VRAM-resident llama.cpp server";
      portKey = "qwen38Vram";
      model = "Qwen3.8-27B-UD-IQ2_XXS.gguf";
      requiresCuda = true;
      dynamicUser = false;
      idleTimeout = "900s";
      readinessTimeout = 600;
      arguments = [
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
        "--jinja"
      ];
    };
    muse-glimmer = {
      description = "Muse Glimmer 30B llama.cpp server";
      portKey = "museGlimmer";
      model = "Muse-Glimmer-30B-Abliterated-Q4_K_M.gguf";
      requiresCuda = true;
      dynamicUser = false;
      idleTimeout = "900s";
      readinessTimeout = 600;
      arguments = [
        "--n-gpu-layers"
        "auto"
        "--fit"
        "on"
        "--fit-target"
        "1536"
        "--ctx-size"
        "32768"
        "--parallel"
        "1"
        "--flash-attn"
        "on"
        "--no-mmproj"
        "--jinja"
        "--chat-template-kwargs"
        ''{"reasoning_strength":"medium"}''
        "--temp"
        "1.0"
        "--top-p"
        "0.95"
        "--top-k"
        "64"
      ];
    };
  };

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

  # GGUF download metadata for /realm/library/model/gguf. llama.cpp profiles
  # above select active files. No fetch or verification job consumes this list.
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
      # currently on disk under /realm/library/model/gguf — re-populate
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
