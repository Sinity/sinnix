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
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "open-webui";
  description = "Open WebUI chat frontend for local models";
  surface = {
    unit = "open-webui.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    autoStart = (
      args.lib.mkOption {
        type = args.lib.types.bool;
        default = true;
        description = "Start Open WebUI automatically at boot.";
      }
    );
  };
  configFn =
    {
      cfg,
      config,
      lib,
      ...
    }:
    {
      services.open-webui = {
        enable = true;
        host = "127.0.0.1";
        port = 8080;
        openFirewall = false;
        environment = {
          OLLAMA_BASE_URL = "http://127.0.0.1:11434";
          WEBUI_AUTH = "False"; # single-user localhost
          ANONYMIZED_TELEMETRY = "False";
          DO_NOT_TRACK = "True";
          ENABLE_OPENAI_API = "False";

          # RAG / document chat via the Ollama embedding model.
          RAG_EMBEDDING_ENGINE = "ollama";
          RAG_EMBEDDING_MODEL = "nomic-embed-text";
          RAG_OLLAMA_BASE_URL = "http://127.0.0.1:11434";

          # Read-aloud / voice-call via the OpenedAI-Speech bridge (TTS service).
          AUDIO_TTS_ENGINE = "openai";
          AUDIO_TTS_OPENAI_API_BASE_URL = "http://127.0.0.1:8000/v1";
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

      sinnix.persistence.system.directories = [ "/var/lib/open-webui" ];
    };
} args
