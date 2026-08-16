# sinnix-ai — on-demand control plane for the local AI services
# (stt, tts, kokoro, ollama, litellm, llama-cpp, muse-glimmer, koboldcpp,
# comfyui, musicgen, ocr, open-webui). The script carries the service registry; this
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

  # Backends declare `partOf = [ "<name>-proxy.service" ]` and NOTHING
  # stronger. PartOf= propagates stop/restart only, which is what frees the
  # GPU when the proxy idles out. BindsTo= (which every backend used to carry
  # alongside it) additionally implies Requires=, so starting a backend by any
  # path -- `sinnix ai start`, its own Restart=on-failure -- also started the
  # proxy directly, outside socket activation. systemd-socket-proxyd then had
  # no inherited listen fds, exited 1 with "Didn't get any sockets passed in",
  # and BindsTo= propagated that failure straight back into the backend. On
  # 2026-08-16 that flap burned muse-glimmer-proxy.socket's activation budget
  # and left port 8083 refusing every connection until a manual reset.
  #
  # `idleTimeout` and `readinessTimeout` are required (no default): the right
  # value differs per backend and a uniform one only ever fit the smallest.
  # systemd-socket-proxyd starts forwarding as soon as ExecStart runs, but
  # backends bind their port only after loading weights (~2s llama-cpp to
  # ~105s comfyui) and the proxy does not retry, so cold connections got a
  # hard "connection refused" -- `requires`+`after` guarantee unit-start
  # ordering, not port-bind. `waitForBackend` blocks ExecStart until the
  # backend accepts TCP; the client meanwhile waits in the `.socket` unit's
  # kernel accept backlog, so a cold request is slow rather than failed.
  mkProxy =
    {
      name,
      backendUnit,
      publicEndpoint,
      backendEndpoint,
      idleTimeout,
      readinessTimeout,
      exclusiveResource ? null,
      dependsOn ? [ ],
    }:
    let
      backendParts = lib.splitString ":" backendEndpoint;
      backendHost = lib.elemAt backendParts 0;
      backendPort = lib.elemAt backendParts 1;
      waitForBackend = pkgs.writeShellApplication {
        name = "${name}-wait-backend";
        runtimeInputs = [ pkgs.coreutils ];
        text = ''
          deadline=$((SECONDS + ${toString readinessTimeout}))
          until (exec 3<>"/dev/tcp/${backendHost}/${backendPort}") 2>/dev/null; do
            if [ "$SECONDS" -ge "$deadline" ]; then
              echo "${name}: timed out after ${toString readinessTimeout}s waiting for ${backendUnit} to listen on ${backendEndpoint}" >&2
              exit 1
            fi
            sleep 0.2
          done
        '';
      };
    in
    {
      sockets.${name} = {
        description = "Socket activation front door for ${backendUnit}";
        wantedBy = [ "sockets.target" ];
        listenStreams = [ publicEndpoint ];
        socketConfig = {
          # systemd's default (200 triggers in 2s) is sized for cheap
          # short-lived handlers. A cold model load holds the accept backlog
          # for as long as readinessTimeout, and an impatient client retrying
          # without backoff can spend that budget in one burst -- after which
          # the socket is dead for good, with no automatic recovery anywhere.
          # Allow a generous burst over a long window instead: the limit
          # exists to catch a genuine activation loop, not client impatience.
          TriggerLimitIntervalSec = "60s";
          TriggerLimitBurst = 2000;
        };
      };
      services.${name} = {
        description = "Idle-aware socket proxy for ${backendUnit}";
        requires = [ backendUnit ];
        after = [ backendUnit ];
        serviceConfig = {
          ExecStartPre = "${waitForBackend}/bin/${name}-wait-backend";
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
            readinessTimeout
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
    # ~10x the cold-start cost of the daily-driver model (~20-23s); idling
    # out is cheaper than a wasted reload.
    idleTimeout = "240s";
    # Ollama is largely exempt from the cold-start-failure problem this probe
    # exists for: the daemon binds its port immediately and loads models
    # lazily per request. 30s is ample for the daemon itself.
    readinessTimeout = 30;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "ollama" ];
  };
  koboldcppProxy = mkProxy {
    name = "koboldcpp-proxy";
    backendUnit = "koboldcpp.service";
    publicEndpoint = "127.0.0.1:5001";
    backendEndpoint = "127.0.0.1:5002";
    # Unmeasurable: koboldcpp-cuda here fails CUDA init with `undefined
    # symbol: cuMemCreate` from koboldcpp_cublas.so on model load, so GPU
    # inference is non-functional regardless of timeout. Sized from its role
    # instead -- the deliberately-slow RAM-offloaded tier for GGUFs larger
    # than ollama's daily driver -- so at least as generous as ollama's 240s.
    idleTimeout = "300s";
    readinessTimeout = 300;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "koboldcpp" ];
  };
  # No exclusiveResource, and that is the point of the engine change. Parakeet
  # int8 through sherpa-onnx transcribes on the CPU fast enough that
  # speech-to-text never needs the GPU (measured on this host: RTF 0.113 on
  # dense speech, 0.002 over a VAD-gated ambient chunk), so unlike the
  # whisper.cpp service it replaces, it is not in the gpu-inference mesh and a
  # transcription can run while a model is resident. The always-on speech lane
  # is exactly the consumer that would otherwise have queued behind an LLM.
  sttProxy = mkProxy {
    name = "stt-proxy";
    backendUnit = "sinnix-stt.service";
    publicEndpoint = "127.0.0.1:8090";
    backendEndpoint = "127.0.0.1:8091";
    # Cold start loads a 650MB encoder, ~2s. The idle window is long because
    # nothing scarce is being held and re-loading it between the turns of one
    # conversation would be the only real cost here.
    idleTimeout = "300s";
    readinessTimeout = 60;
    dependsOn = [ "stt" ];
  };
  # No exclusiveResource: the reranker runs CPU-pinned (gpuLayers = 0,
  # hosts/sinnix-prime/default.nix). It is not VRAM-free -- the CUDA-linked
  # binary still allocates ~680-740MiB even at -ngl 0 -- but far below the
  # ~1610MiB it held fully offloaded, so it stays out of the gpu-inference
  # mesh and coexists with a resident ollama/koboldcpp session.
  llamaCppProxy = mkProxy {
    name = "llama-cpp-proxy";
    backendUnit = "llama-cpp.service";
    publicEndpoint = "127.0.0.1:8081";
    backendEndpoint = "127.0.0.1:8082";
    # Cold /v1/rerank for the 0.6B reranker is ~1-3s; 30s is ~10-30x headroom
    # for both timeouts.
    idleTimeout = "30s";
    readinessTimeout = 30;
    dependsOn = [ "llama-cpp" ];
  };
  museGlimmerProxy = mkProxy {
    name = "muse-glimmer-proxy";
    backendUnit = "muse-glimmer.service";
    publicEndpoint = "127.0.0.1:8083";
    backendEndpoint = "127.0.0.1:8084";
    idleTimeout = "900s";
    readinessTimeout = 600;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "muse-glimmer" ];
  };
  litellmProxy = mkProxy {
    name = "litellm-proxy";
    backendUnit = "litellm.service";
    publicEndpoint = "127.0.0.1:4000";
    backendEndpoint = "127.0.0.1:4001";
    # Lightweight gateway process, unmeasured; kept at the baseline default.
    idleTimeout = "30s";
    readinessTimeout = 30;
    dependsOn = [ "ollama-proxy" ];
  };
  # No exclusiveResource: Kokoro is CPU-only (modules/services/kokoro.nix)
  # and must stay answerable regardless of which CUDA backend, if any,
  # currently holds gpu-inference.
  kokoroProxy = mkProxy {
    name = "kokoro-proxy";
    backendUnit = "podman-kokoro.service";
    publicEndpoint = "127.0.0.1:8890";
    backendEndpoint = "127.0.0.1:8891";
    # Unmeasured; kept at the baseline default.
    idleTimeout = "30s";
    readinessTimeout = 30;
  };

  # ComfyUI, TTS (OpenedAI-Speech), MusicGen, and OCR are OCI containers with
  # CDI GPU passthrough (modules/services/{comfyui,tts,musicgen,ocr}.nix), but
  # `virtualisation.oci-containers` generates an ordinary
  # systemd.services.podman-<name> unit, so they proxy exactly like the native
  # backends. The one container-specific requirement: the container's own
  # `ports` mapping must sit on the backend port, leaving the public port to
  # systemd-socket-proxyd.
  comfyuiProxy = mkProxy {
    name = "comfyui-proxy";
    backendUnit = "podman-comfyui.service";
    publicEndpoint = "127.0.0.1:8188";
    backendEndpoint = "127.0.0.1:8189";
    # Cold start to a 200 from `/` is ~105s: the
    # mmartial/comfyui-nvidia-docker image re-resolves its Python venv on
    # every launch, re-downloading a ~930MB torch wheel, which dominates the
    # cost before any checkpoint loads. 900s idle because a real ComfyUI
    # session (queue a generation, wait on output) is a long round trip.
    idleTimeout = "900s";
    # 180s readiness: headroom over the ~105s cold start, while still failing
    # loud on a stuck container instead of hanging for the full idle timeout.
    readinessTimeout = 180;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "comfyui" ];
  };
  ttsProxy = mkProxy {
    name = "tts-proxy";
    backendUnit = "podman-openedai-speech.service";
    publicEndpoint = "127.0.0.1:8000";
    backendEndpoint = "127.0.0.1:8001";
    # Cold start to a 200 from /v1/audio/speech (Piper voice) is ~17s; XTTS
    # voice cloning is heavier. 300s/60s covers headroom for both voices.
    idleTimeout = "300s";
    readinessTimeout = 60;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "tts" ];
  };
  musicgenProxy = mkProxy {
    name = "musicgen-proxy";
    backendUnit = "podman-musicgen.service";
    publicEndpoint = "127.0.0.1:8010";
    backendEndpoint = "127.0.0.1:8011";
    # Unmeasured (disabled on this host). Same all-in-one Gradio+PyTorch
    # toolkit shape as ComfyUI, so sized to the same tier.
    idleTimeout = "900s";
    readinessTimeout = 180;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "musicgen" ];
  };
  ocrProxy = mkProxy {
    name = "ocr-proxy";
    backendUnit = "podman-ocr.service";
    publicEndpoint = "127.0.0.1:8020";
    backendEndpoint = "127.0.0.1:8021";
    # Unmeasured (disabled on this host). marker-api's Surya weights are
    # small (~1-2GB) next to ComfyUI's checkpoint tree, so sized to the tts
    # container tier.
    idleTimeout = "300s";
    readinessTimeout = 60;
    exclusiveResource = "gpu-inference";
    dependsOn = [ "ocr" ];
  };

  # ── GPU-inference exclusivity mesh ───────────────────────────────────────
  # Every backend below claims the GPU exclusively. Naming them once here and
  # computing the pairwise Conflicts= matrix from that list keeps a newly
  # admitted backend from landing asymmetric. Each side's Conflicts= is gated
  # on its OWN service's enable flag only, never the peer's: a Conflicts=
  # entry naming an undefined unit is a harmless no-op in systemd, and
  # cross-referencing peer enable state would make eight modules' correctness
  # depend on read-order.
  gpuInferenceBackends = {
    ollama = {
      enable = config.sinnix.services.ollama.enable;
      service = "ollama.service";
      proxy = "ollama-proxy.service";
    };
    muse-glimmer = {
      enable = config.sinnix.services.muse-glimmer.enable;
      service = "muse-glimmer.service";
      proxy = "muse-glimmer-proxy.service";
    };
    koboldcpp = {
      enable = config.sinnix.services.koboldcpp.enable;
      service = "koboldcpp.service";
      proxy = "koboldcpp-proxy.service";
    };
    # llama-cpp (the reranker) is not a member: it runs CPU-pinned
    # (gpuLayers = 0) and coexists with every backend here.
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
          peerUnits = lib.concatMap (peerName: [
            gpuInferenceBackends.${peerName}.service
            gpuInferenceBackends.${peerName}.proxy
          ]) (lib.filter (n: n != name) (lib.attrNames gpuInferenceBackends));
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
    (lib.mkIf config.sinnix.services.stt.enable sttProxy.sockets)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.sockets)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.sockets)
    (lib.mkIf config.sinnix.services.llama-cpp.enable llamaCppProxy.sockets)
    (lib.mkIf config.sinnix.services.muse-glimmer.enable museGlimmerProxy.sockets)
    (lib.mkIf config.sinnix.services.comfyui.enable comfyuiProxy.sockets)
    (lib.mkIf config.sinnix.services.tts.enable ttsProxy.sockets)
    (lib.mkIf config.sinnix.services.musicgen.enable musicgenProxy.sockets)
    (lib.mkIf config.sinnix.services.ocr.enable ocrProxy.sockets)
  ];
  systemd.services = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.services)
    (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.services)
    (lib.mkIf config.sinnix.services.stt.enable sttProxy.services)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.services)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.services)
    (lib.mkIf config.sinnix.services.llama-cpp.enable llamaCppProxy.services)
    (lib.mkIf config.sinnix.services.muse-glimmer.enable museGlimmerProxy.services)
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
    (lib.mkIf config.sinnix.services.stt.enable {
      stt-proxy = sttProxy.runtimeSurface;
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
    (lib.mkIf config.sinnix.services.muse-glimmer.enable {
      muse-glimmer-proxy = museGlimmerProxy.runtimeSurface;
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
