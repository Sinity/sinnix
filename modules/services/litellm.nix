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
# no master key. Native loopback clients remain trusted; the HTTP application
# checks Host and browser provenance before body reads or dispatch. The wrappers
# still send a dummy bearer token because Claude Code
# requires a non-empty ANTHROPIC_AUTH_TOKEN.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkServiceModule {
  name = "litellm";
  description = "LiteLLM gateway (Anthropic↔OpenAI) for local models";
  docs = "docs/local-ai-activation.md";
  surface = {
    ai = {
      backendKind = "native";
      requiresCuda = false;
    };
    unit = "litellm.service";
    # Uncapped memory: a single 1M-token request is buffered in the proxy while
    # streaming, so a hard MemoryMax could kill it mid-response (same reasoning
    # as ollama/open-webui).
    resourceClass = "ordinary";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:${toString helpers.data.ports.litellm.public}";
      backendEndpoint = "127.0.0.1:${toString helpers.data.ports.litellm.backend}";
      # Lightweight gateway process, unmeasured; kept at the baseline default.
      idleTimeout = "30s";
      readinessTimeout = 30;
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = false;
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
    let
      listenerPorts = [
        helpers.data.ports.litellm.public
        helpers.data.ports.litellm.backend
      ];
      corsOrigins = lib.concatMap (host: map (port: "http://${host}:${toString port}") listenerPorts) [
        "127.0.0.1"
        "localhost"
        "[::1]"
      ];
      guardedPackage = pkgs.litellm.overridePythonAttrs (old: {
        postPatch = (old.postPatch or "") + ''
          grep -F 'app.add_middleware(SecurityHeadersMiddleware)' litellm/proxy/proxy_server.py >/dev/null
          cp ${../../pkgs/sinnix-litellm-boundary/boundary.py} litellm/proxy/sinnix_browser_boundary.py
          cat >> litellm/proxy/proxy_server.py <<'PYTHON'

          from .sinnix_browser_boundary import BrowserBoundary
          app.add_middleware(BrowserBoundary)
          PYTHON
        '';
      });
    in
    {
      services.litellm = {
        package = guardedPackage;
        enable = true;
        host = "127.0.0.1";
        # The public port is reserved for the socket-activated front door.
        port = helpers.data.ports.litellm.backend;
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

      # Backends are socket-activated independently by their own public
      # endpoints. Requiring Ollama here would start its GPU occupant whenever
      # LiteLLM starts and evict direct backends such as Muse Glimmer.
      systemd.services.litellm = {
        environment = {
          SINNIX_LITELLM_PORTS = lib.concatMapStringsSep "," toString listenerPorts;
          LITELLM_CORS_ORIGINS = lib.concatStringsSep "," corsOrigins;
          LITELLM_CORS_ALLOW_CREDENTIALS = "false";
        };
        wantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);
      };
    };
} args
