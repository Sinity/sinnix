# LiteLLM — local model gateway bridging the Anthropic and OpenAI dialects.
#
# Claude Code speaks ONLY the Anthropic Messages API (`POST /v1/messages`);
# the local engines (Ollama et al.) speak ONLY the OpenAI API. LiteLLM is the
# translator that lets the real Claude Code harness drive a local model: it
# exposes BOTH `/v1/messages` (Anthropic) and `/v1/chat/completions` (OpenAI)
# on one loopback port and forwards to Ollama. The `claude-local` and
# `codex-local` wrappers (modules/features/dev/agent-tools.nix) both target it,
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
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { ... }:
    {
      services.litellm = {
        enable = true;
        host = "127.0.0.1";
        port = 4000; # 8080 is taken by open-webui
        openFirewall = false;
        settings = {
          # Model names exposed to the agents. Backed by the Ollama hub on
          # :11434; edit here to add/swap local models (the `*-local` wrappers
          # default to `local-llama`).
          model_list = [
            {
              model_name = "local-llama";
              litellm_params = {
                model = "ollama_chat/huihui_ai/llama3.2-abliterate";
                api_base = "http://127.0.0.1:11434";
              };
            }
            {
              model_name = "local-vision";
              litellm_params = {
                model = "ollama/llava";
                api_base = "http://127.0.0.1:11434";
              };
            }
          ];
          litellm_settings = {
            # Silently drop sampling params the local backend doesn't support
            # instead of 400-ing the whole request (Claude Code/Codex send a
            # superset of what Ollama accepts).
            drop_params = true;
          };
        };
      };

      # Gateway is useless without the backend; order startup after it.
      systemd.services.litellm.after = [ "ollama.service" ];
    };
} args
