# LiteLLM — local model gateway bridging the Anthropic and OpenAI dialects.
#
# Claude Code speaks ONLY the Anthropic Messages API (`POST /v1/messages`);
# the local engines (Ollama et al.) speak ONLY the OpenAI API. LiteLLM is the
# translator that lets the real Claude Code harness drive a local model: it
# exposes BOTH `/v1/messages` (Anthropic) and `/v1/chat/completions` (OpenAI)
# on one loopback port and forwards to Ollama. The `claude-local` and
# `codex-local` wrappers (modules/features/dev/agents/clis.nix) both target it,
# so local model names live in exactly one place — the `model_list` below.
#
# Stateless gateway: the only on-disk state is the UI scratch dir and the
# tiktoken cache (seeded from the Nix store, no outbound fetch at boot), both
# under /var/lib/litellm via the upstream module's StateDirectory. No secrets,
# no master key — it binds 127.0.0.1 only, so requests on the loopback are
# trusted (the wrappers still send a dummy bearer token because Claude Code
# requires a non-empty ANTHROPIC_AUTH_TOKEN).
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "litellm";
  description = "LiteLLM gateway (Anthropic↔OpenAI) for local models";
  surface = {
    unit = "litellm.service";
    # Uncapped memory: a single 1M-token request is buffered in the proxy while
    # streaming, so a hard MemoryMax could kill it mid-response (same reasoning
    # as ollama/open-webui).
    resourceClass = "interactive-agent";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:4000";
      backendEndpoint = "127.0.0.1:4001";
      idleTimeout = "30s";
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
      description = "Start LiteLLM automatically at boot.";
    };
  };
  configFn =
    {
      cfg,
      lib,
      helpers,
      ...
    }:
    {
      services.litellm = {
        enable = true;
        host = "127.0.0.1";
        # 4000 is reserved for the socket-activated front door.
        port = 4001;
        openFirewall = false;
        settings = {
          # Model names exposed to the agents, backed by the Ollama hub on
          # :11434. Sourced from flake/data/local-models.nix (the roster
          # shared with ollama.nix's loadModels and open-webui.nix's
          # RAG_EMBEDDING_MODEL) — edit the roster there, not here. The
          # `*-local` wrappers default to `local-chat`.
          model_list = helpers.data.localModels.litellmModelList;
          litellm_settings = {
            # Silently drop sampling params the local backend doesn't support
            # instead of 400-ing the whole request (Claude Code/Codex send a
            # superset of what Ollama accepts).
            drop_params = true;
          };
        };
      };

      # Gateway is useless without the backend; order startup after it.
      systemd.services.litellm = {
        after = [ "ollama.service" ];
        requires = [ "ollama-proxy.service" ];
        partOf = [ "litellm-proxy.service" ];
        bindsTo = [ "litellm-proxy.service" ];
        wantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);
      };
    };
} args
