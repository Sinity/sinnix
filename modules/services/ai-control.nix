# sinnix-ai — on-demand control plane for the local AI services
# (whisper, tts, kokoro, ollama, litellm, llama-cpp, koboldcpp, comfyui,
# musicgen, ocr, open-webui). The script carries the service registry; this
# module only installs it. See scripts/sinnix-ai.
{
  config,
  lib,
  pkgs,
  helpers,
  ...
}:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  systemdSocketProxyd = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd";

  # `idleTimeout` is required (no default): every call site below has to
  # state and justify its own number instead of silently inheriting a
  # uniform 30s that only ever fit the smallest backend (sinnix-mba).
  mkProxy =
    {
      name,
      backendUnit,
      publicEndpoint,
      backendEndpoint,
      idleTimeout,
      exclusiveResource ? null,
      dependsOn ? [ ],
    }:
    {
      sockets.${name} = {
        description = "Socket activation front door for ${backendUnit}";
        wantedBy = [ "sockets.target" ];
        listenStreams = [ publicEndpoint ];
      };
      services.${name} = {
        description = "Idle-aware socket proxy for ${backendUnit}";
        requires = [ backendUnit ];
        after = [ backendUnit ];
        serviceConfig = {
          ExecStart = "${systemdSocketProxyd} --exit-idle-time=${idleTimeout} ${backendEndpoint}";
          Restart = "no";
        };
      };
      runtimeSurface = {
        unit = "${name}.socket";
        kind = "socket";
        resourceClass = "interactive-agent";
        activation = {
          mode = "socket-proxy";
          inherit
            publicEndpoint
            backendEndpoint
            exclusiveResource
            dependsOn
            idleTimeout
            ;
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };
    };

  ollamaProxy = mkProxy {
    name = "ollama-proxy";
    backendUnit = "ollama.service";
    publicEndpoint = "127.0.0.1:11434";
    backendEndpoint = "127.0.0.1:11435";
    # Measured 2026-08-13: a cold /api/generate round trip for the 7.2GB
    # daily-driver model (gemma4:12b-it-qat) took ~20-23s end to end (daemon
    # start + weight load + first token). The 18GB qwen3:30b model overflows
    # the 3080's 10GB VRAM and did not finish loading even after 300s -- it
    # hit ollama's own 5-minute OLLAMA_LOAD_TIMEOUT before producing a
    # token. That is a load-timeout problem, not an idle-timeout one, and is
    # tracked separately (bd issue filed alongside this change) rather than
    # fixed here. 240s is ~10x the measured daily-driver cost: an idle-out
    # is never worse than a wasted reload for the model this host actually
    # drives chat sessions with.
    idleTimeout = "240s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "ollama" ];
  };
  koboldcppProxy = mkProxy {
    name = "koboldcpp-proxy";
    backendUnit = "koboldcpp.service";
    publicEndpoint = "127.0.0.1:5001";
    backendEndpoint = "127.0.0.1:5002";
    # Could NOT be measured directly: koboldcpp-cuda on this host currently
    # fails CUDA library init with `undefined symbol: cuMemCreate` from
    # koboldcpp_cublas.so the moment a model is loaded -- a pre-existing
    # environment breakage unrelated to this change (bd issue filed
    # alongside this change; koboldcpp is currently non-functional for GPU
    # inference regardless of idle timeout). Picked from koboldcpp's stated
    # role instead: the deliberately-slow RAM-offloaded tier for GGUFs
    # larger than ollama's daily driver (see koboldcpp.nix's header), so
    # this is at least as generous as ollama's measured 240s.
    idleTimeout = "300s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "koboldcpp" ];
  };
  whisperProxy = mkProxy {
    name = "whisper-proxy";
    backendUnit = "whisper-server.service";
    publicEndpoint = "127.0.0.1:8090";
    backendEndpoint = "127.0.0.1:8091";
    # Measured 2026-08-13: a cold /v1/audio/transcriptions round trip for
    # the configured base.en model (147MB) took ~2s end to end. An order of
    # magnitude of headroom already exists at 30s -- kept unchanged.
    idleTimeout = "30s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "whisper" ];
  };
  llamaCppProxy = mkProxy {
    name = "llama-cpp-proxy";
    backendUnit = "llama-cpp.service";
    publicEndpoint = "127.0.0.1:8081";
    backendEndpoint = "127.0.0.1:8082";
    # Measured 2026-08-13: a cold /v1/rerank round trip for the 0.6B
    # reranker took ~1-3s end to end, matching llama-cpp.nix's existing
    # "reloads in about a second" note. 30s is already ~10-30x headroom --
    # kept unchanged.
    idleTimeout = "30s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "llama-cpp" ];
  };
  litellmProxy = mkProxy {
    name = "litellm-proxy";
    backendUnit = "litellm.service";
    publicEndpoint = "127.0.0.1:4000";
    backendEndpoint = "127.0.0.1:4001";
    # litellm.nix belongs to a different lane in this change; left at the
    # prior uniform default rather than guessed at.
    idleTimeout = "30s";
    dependsOn = [ "ollama-proxy" ];
  };
  # Deliberately no exclusiveResource here: Kokoro is CPU-only
  # (modules/services/kokoro.nix) and must stay answerable regardless of
  # which CUDA backend, if any, currently holds gpu-inference.
  kokoroProxy = mkProxy {
    name = "kokoro-proxy";
    backendUnit = "podman-kokoro.service";
    publicEndpoint = "127.0.0.1:8890";
    backendEndpoint = "127.0.0.1:8891";
    # kokoro.nix belongs to a different lane in this change; left at the
    # prior uniform default rather than guessed at.
    idleTimeout = "30s";
  };

  # ComfyUI, TTS (OpenedAI-Speech), MusicGen, and OCR are OCI containers with
  # CDI GPU passthrough (modules/services/{comfyui,tts,musicgen,ocr}.nix).
  # They were previously left off the mkProxy mesh on the theory that a
  # container "has no idle-aware backend to proxy" -- that theory doesn't
  # hold: `virtualisation.oci-containers` generates an ordinary
  # systemd.services.podman-<name> unit, controllable exactly like
  # ollama.service. The only real difference is that the container's own
  # `ports` mapping has to move off the public port so systemd-socket-proxyd
  # can sit in front of it, same as the native backends' `port` config
  # moving off the socket-activated front door. All four now join the same
  # public/backend split (flake/data/ports.nix) and the same
  # partOf/bindsTo/idle-teardown shape as ollama/koboldcpp/whisper/llama-cpp.
  comfyuiProxy = mkProxy {
    name = "comfyui-proxy";
    backendUnit = "podman-comfyui.service";
    publicEndpoint = "127.0.0.1:8188";
    backendEndpoint = "127.0.0.1:8189";
    # Measured 2026-08-13: cold start to a 200 from `/` took ~105s. The
    # mmartial/comfyui-nvidia-docker image re-resolves its Python venv on
    # every launch and re-downloaded a 930MB torch wheel during this
    # measurement even though a working torch was already installed --
    # that reinstall-on-every-launch behavior is the dominant cost, before
    # any checkpoint has even been loaded. 900s (15min) per the operator's
    # ask for generous container timeouts: a real ComfyUI session (queueing
    # a generation, waiting on output) is a long round trip on top of the
    # cold start itself.
    idleTimeout = "900s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "comfyui" ];
  };
  ttsProxy = mkProxy {
    name = "tts-proxy";
    backendUnit = "podman-openedai-speech.service";
    publicEndpoint = "127.0.0.1:8000";
    backendEndpoint = "127.0.0.1:8001";
    # Measured 2026-08-13: cold start to a 200 from /v1/audio/speech (Piper
    # voice) took ~17s. XTTS voice cloning was not separately measured (a
    # heavier model, likely slower); 300s covers headroom for both voices.
    idleTimeout = "300s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "tts" ];
  };
  musicgenProxy = mkProxy {
    name = "musicgen-proxy";
    backendUnit = "podman-musicgen.service";
    publicEndpoint = "127.0.0.1:8010";
    backendEndpoint = "127.0.0.1:8011";
    # Disabled on this host (musicgen.enable = false) -- not measured. Same
    # all-in-one Gradio+PyTorch toolkit shape as ComfyUI
    # (rsxdalv/tts-generation-webui vs. mmartial/comfyui-nvidia-docker), so
    # treated as the same tier: 900s.
    idleTimeout = "900s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "musicgen" ];
  };
  ocrProxy = mkProxy {
    name = "ocr-proxy";
    backendUnit = "podman-ocr.service";
    publicEndpoint = "127.0.0.1:8020";
    backendEndpoint = "127.0.0.1:8021";
    # Disabled on this host (ocr.enable = false) -- not measured.
    # marker-api's Surya weights are comparatively small (~1-2GB) next to
    # ComfyUI's checkpoint tree, so treated like the tts container tier:
    # 300s.
    idleTimeout = "300s";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "ocr" ];
  };

  # ── GPU-inference exclusivity mesh ───────────────────────────────────────
  # Every backend below claims the GPU exclusively. Naming them once here and
  # computing the pairwise Conflicts= matrix from that list means a newly
  # admitted backend cannot land asymmetric -- llama-cpp shipped resident
  # for two days before symmetric Conflicts= landed (sinnix-w9l/e2fb0af),
  # and the same gap existed for the container lane until this change
  # (sinnix-joac) folded it into the same mesh instead of a parallel
  # container-only Conflicts= scheme. Each side's Conflicts= is gated on its
  # OWN service's enable flag only (never the peer's): a Conflicts= entry
  # naming a unit that never gets defined (peer disabled) is a harmless
  # no-op in systemd, so there is nothing to gain by cross-referencing peer
  # enable state, and doing so would make eight modules' correctness depend
  # on read-order.
  gpuInferenceBackends = {
    ollama = {
      enable = config.sinnix.services.ollama.enable;
      service = "ollama.service";
      proxy = "ollama-proxy.service";
    };
    koboldcpp = {
      enable = config.sinnix.services.koboldcpp.enable;
      service = "koboldcpp.service";
      proxy = "koboldcpp-proxy.service";
    };
    whisper = {
      enable = config.sinnix.services.whisper.enable;
      service = "whisper-server.service";
      proxy = "whisper-proxy.service";
    };
    llama-cpp = {
      enable = config.sinnix.services.llama-cpp.enable;
      service = "llama-cpp.service";
      proxy = "llama-cpp-proxy.service";
    };
    comfyui = {
      enable = config.sinnix.services.comfyui.enable;
      service = "podman-comfyui.service";
      proxy = "comfyui-proxy.service";
    };
    tts = {
      enable = config.sinnix.services.tts.enable;
      service = "podman-openedai-speech.service";
      proxy = "tts-proxy.service";
    };
    musicgen = {
      enable = config.sinnix.services.musicgen.enable;
      service = "podman-musicgen.service";
      proxy = "musicgen-proxy.service";
    };
    ocr = {
      enable = config.sinnix.services.ocr.enable;
      service = "podman-ocr.service";
      proxy = "ocr-proxy.service";
    };
  };
  gpuInferenceConflicts = lib.mkMerge (
    lib.mapAttrsToList (
      name: backend:
      lib.mkIf backend.enable (
        let
          peerUnits = lib.concatMap
            (peerName: [
              gpuInferenceBackends.${peerName}.service
              gpuInferenceBackends.${peerName}.proxy
            ])
            (lib.filter (n: n != name) (lib.attrNames gpuInferenceBackends));
        in
        {
          ${lib.removeSuffix ".service" backend.service}.conflicts = peerUnits;
          ${lib.removeSuffix ".service" backend.proxy}.conflicts = peerUnits;
        }
      )
    ) gpuInferenceBackends
  );
in
{
  environment.systemPackages = [ scriptPkgs.sinnix-ai ];
  systemd.sockets = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.sockets)
    (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.sockets)
    (lib.mkIf config.sinnix.services.whisper.enable whisperProxy.sockets)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.sockets)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.sockets)
    (lib.mkIf config.sinnix.services.llama-cpp.enable llamaCppProxy.sockets)
    (lib.mkIf config.sinnix.services.comfyui.enable comfyuiProxy.sockets)
    (lib.mkIf config.sinnix.services.tts.enable ttsProxy.sockets)
    (lib.mkIf config.sinnix.services.musicgen.enable musicgenProxy.sockets)
    (lib.mkIf config.sinnix.services.ocr.enable ocrProxy.sockets)
  ];
  systemd.services = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.services)
    (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.services)
    (lib.mkIf config.sinnix.services.whisper.enable whisperProxy.services)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.services)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.services)
    (lib.mkIf config.sinnix.services.llama-cpp.enable llamaCppProxy.services)
    (lib.mkIf config.sinnix.services.comfyui.enable comfyuiProxy.services)
    (lib.mkIf config.sinnix.services.tts.enable ttsProxy.services)
    (lib.mkIf config.sinnix.services.musicgen.enable musicgenProxy.services)
    (lib.mkIf config.sinnix.services.ocr.enable ocrProxy.services)
    gpuInferenceConflicts
  ];
  sinnix.runtime.surfaces = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable {
      ollama-proxy = ollamaProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.koboldcpp.enable {
      koboldcpp-proxy = koboldcppProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.whisper.enable {
      whisper-proxy = whisperProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.litellm.enable {
      litellm-proxy = litellmProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.kokoro.enable {
      kokoro-proxy = kokoroProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.llama-cpp.enable {
      llama-cpp-proxy = llamaCppProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.comfyui.enable {
      comfyui-proxy = comfyuiProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.tts.enable {
      tts-proxy = ttsProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.musicgen.enable {
      musicgen-proxy = musicgenProxy.runtimeSurface;
    })
    (lib.mkIf config.sinnix.services.ocr.enable {
      ocr-proxy = ocrProxy.runtimeSurface;
    })
  ];
}
