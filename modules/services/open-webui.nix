# Open WebUI — ChatGPT-style web frontend for the local Ollama hub.
#
# Loopback upstream (127.0.0.1:8080), republished by the hub on its tailnet
# frontend. Single-operator mode disables the login form. RAG/document
# chat uses the Ollama embedding model; TTS read-aloud / voice-call points at the
# enabled local speech provider. STT is left at Open WebUI's
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
  activation.publicEndpoint = "127.0.0.1:${toString helpers.data.ports.openWebui}";
  stateDirectories = [ "/var/lib/open-webui" ];
  requiresCuda = false;
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = false;
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
    let
      ttsProvider =
        if config.sinnix.services.tts.enable then
          {
            port = helpers.data.ports.tts.public;
            model = "tts-1";
            voice = "alloy";
          }
        else if config.sinnix.services.kokoro.enable then
          {
            port = helpers.data.ports.kokoro.public;
            model = "kokoro";
            voice = "af_heart";
          }
        else
          null;
      resolveIdentity =
        (import ../lib/tailnet-bind.nix {
          inherit pkgs lib;
          interface = config.sinnix.services.tailscale.interfaceName;
        })
          "open-webui-resolve-identity"
          "SINNIX_HUB_TAILNET_IP"
          "open-webui";
      guardedPackage = pkgs.open-webui.overridePythonAttrs (old: {
        postPatch = (old.postPatch or "") + ''
          test -f backend/open_webui/main.py
          cp ${../../pkgs/sinnix-litellm-boundary/boundary.py} backend/open_webui/sinnix_browser_boundary.py
          cat >> backend/open_webui/main.py <<'PYTHON'

          from .sinnix_browser_boundary import BrowserBoundary
          app.add_middleware(
              BrowserBoundary,
              allowed_ports={int(port) for port in os.environ["SINNIX_WEBUI_PORTS"].split(",")},
              allowed_hosts={
                  "localhost", "127.0.0.1", "::1", os.environ["SINNIX_WEBUI_HOSTNAME"],
                  os.environ["SINNIX_HUB_TAILNET_IP"], os.environ["SINNIX_HUB_DNS_NAME"],
              },
          )
          PYTHON
        '';
      });
    in
    {
      sinnix.runtime.dataStores.open-webui-state = {
        path = "/var/lib/open-webui";
        class = "canonical";
      };

      services.open-webui = {
        enable = true;
        package = guardedPackage;
        host = "127.0.0.1";
        port = helpers.data.ports.openWebui;
        openFirewall = false;
        environment = {
          SINNIX_WEBUI_HOSTNAME = config.networking.hostName;
          SINNIX_WEBUI_PORTS = lib.concatStringsSep "," (
            map toString [
              helpers.data.ports.openWebui
              config.sinnix.services.hub.frontends.open-webui.port
            ]
          );
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
        }
        // lib.optionalAttrs (ttsProvider != null) {
          # Defaults seed new stores; existing operator settings remain owned
          # by Open WebUI's configuration API.
          AUDIO_TTS_ENGINE = "openai";
          AUDIO_TTS_OPENAI_API_BASE_URL = "http://127.0.0.1:${toString ttsProvider.port}/v1";
          AUDIO_TTS_OPENAI_API_KEY = "sk-local";
          AUDIO_TTS_MODEL = ttsProvider.model;
          AUDIO_TTS_VOICE = ttsProvider.voice;
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
        # The verified identity resolver reads interface addresses via rtnetlink.
        RestrictAddressFamilies = lib.mkAfter [ "AF_NETLINK" ];
        ExecStartPre = [ "${resolveIdentity} /run/open-webui/bind.env" ];
        EnvironmentFile = [ "-/run/open-webui/bind.env" ];
        DynamicUser = lib.mkForce false;
        User = "open-webui";
        Group = "open-webui";
      };
      systemd.services.open-webui.wantedBy = lib.mkIf (!cfg.autoStart) (lib.mkForce [ ]);

    };
} args
