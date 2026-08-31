# Open WebUI — ChatGPT-style web frontend for the local Ollama hub.
#
# Localhost-only (127.0.0.1:8080), single-user → auth disabled. RAG/document
# chat uses the Ollama embedding model; TTS read-aloud / voice-call points at the
# OpenedAI-Speech bridge (sinnix.services.tts). STT is left at Open WebUI's
# built-in local engine.
#
# State (chat history, RAG vector DB — small, not model weights) stays in
# /var/lib/open-webui and is persisted across the impermanence root-wipe. The
# upstream unit uses DynamicUser + StateDirectory (→ /var/lib/private/...), which
# is awkward to persist; we override to a dedicated static user so the state dir
# is a plain owned path.
{
  mkAiService,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkAiService {
  name = "open-webui";
  description = "Open WebUI chat frontend for local models";
  docs = "docs/local-ai-activation.md";
  unit = "open-webui.service";
  endpoint = "127.0.0.1:${toString helpers.data.ports.openWebui}";
  stateDirectories = [ "/var/lib/open-webui" ];
  requiresCuda = false;
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = true;
      description = "Start Open WebUI automatically at boot.";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      helpers,
      ...
    }:
    {
      services.open-webui = {
        enable = true;
        host = "127.0.0.1";
        port = helpers.data.ports.openWebui;
        openFirewall = false;
        environment = {
          OLLAMA_BASE_URL = "http://127.0.0.1:${toString helpers.data.ports.ollama.public}";
          WEBUI_AUTH = "False"; # single-user localhost
          ANONYMIZED_TELEMETRY = "False";
          DO_NOT_TRACK = "True";
          # LiteLLM lanes in the model picker alongside the raw ollama tags —
          # this is how the direct llama.cpp endpoints (local-glimmer,
          # local-qwen38-vram) are reachable from the WebUI at all.
          ENABLE_OPENAI_API = "True";
          OPENAI_API_BASE_URLS = "http://127.0.0.1:${toString helpers.data.ports.litellm.public}/v1";
          OPENAI_API_KEYS = "sk-local";

          # RAG / document chat via the Ollama embedding model. Sourced from
          # flake/data/local-models.nix (the roster shared with ollama.nix's
          # loadModels and litellm.nix's model_list) — edit the roster
          # there, not here.
          RAG_EMBEDDING_ENGINE = "ollama";
          RAG_EMBEDDING_MODEL = helpers.data.localModels.ragEmbeddingOllamaTag;
          RAG_OLLAMA_BASE_URL = "http://127.0.0.1:${toString helpers.data.ports.ollama.public}";

          # Read-aloud / voice-call via the OpenedAI-Speech bridge (TTS service).
          AUDIO_TTS_ENGINE = "openai";
          AUDIO_TTS_OPENAI_API_BASE_URL = "http://127.0.0.1:${toString helpers.data.ports.tts.public}/v1";
          AUDIO_TTS_OPENAI_API_KEY = "sk-local";
          AUDIO_TTS_MODEL = "tts-1";
          AUDIO_TTS_VOICE = "alloy";
        };
      };

      # Dedicated static user so /var/lib/open-webui is a plain owned directory
      # we can persist (chat history must survive reboots).
      users.users.open-webui = {
        isSystemUser = true;
        group = "open-webui";
        home = "/var/lib/open-webui";
      };
      users.groups.open-webui = { };
      systemd.services.open-webui.serviceConfig = {
        DynamicUser = lib.mkForce false;
        User = "open-webui";
        Group = "open-webui";
      };
      systemd.services.open-webui.wantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);

    };
} args
