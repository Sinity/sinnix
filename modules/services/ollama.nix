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
        description = "Start Ollama automatically at boot.";
      }
    );
    loadModels = (
      args.lib.mkOption {
        type = args.lib.types.listOf args.lib.types.str;
        default = [
          # Abliterated/uncensored LLM that fits ~10 GB at Q4. Edit to taste; a
          # failed pull only fails the loader oneshot, not the system.
          "huihui_ai/llama3.2-abliterate"
          # Vision (VLM)
          "llava"
          # Embeddings for Open WebUI RAG / document chat
          "nomic-embed-text"
        ];
        description = "Models pre-pulled by the ollama-model-loader oneshot.";
      }
    );
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
      modelsDir = "${config.sinnix.paths.librariesRoot}/model/ollama";
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
        port = 11434;
        openFirewall = false;
        models = modelsDir;
        loadModels = cfg.loadModels;
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
        "d ${config.sinnix.paths.librariesRoot}/model 0755 ${user} users -"
        "d ${modelsDir} 0755 ollama ollama -"
      ];

      environment.systemPackages = [ pkgs.ollama-cuda ]; # `ollama` CLI on PATH

      systemd.services = lib.mkIf (!cfg.autoStart) {
        ollama.wantedBy = lib.mkForce [ ];
        ollama-model-loader.wantedBy = lib.mkForce [ ];
      };
    };
} args
