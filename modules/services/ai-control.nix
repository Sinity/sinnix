# sinnix-ai — on-demand control plane for the local AI services
# (stt, tts, kokoro, ollama, litellm, llama-cpp, muse-glimmer, qwen38-vram,
# koboldcpp, comfyui, musicgen, ocr, open-webui). The module declares the live
# service and runtime surfaces; scripts/sinnix-ai is a thin inventory/action
# reader.
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

  # Backends declare `partOf` and NOTHING stronger. PartOf propagates
  # stop/restart only, which frees the GPU when the proxy idles out. BindsTo
  # also implies Requires, so any backend start pulls in the proxy outside
  # socket activation, where systemd-socket-proxyd has no listen fds, exits 1,
  # and propagates that failure back into the backend.
  #
  # idleTimeout/readinessTimeout have no default: the right value differs per
  # backend. The proxy forwards as soon as ExecStart runs, but backends bind
  # their port only after loading weights (~2s to ~105s) and it does not
  # retry -- requires+after order unit starts, not port binds. waitForBackend
  # gates ExecStart on a real TCP accept, so a cold request is slow, not
  # refused.
  mkProxy =
    name:
    {
      backendUnit,
      ports,
      idleTimeout,
      readinessTimeout,
      gpuExclusive ? false,
      ...
    }:
    let
      publicEndpoint = "127.0.0.1:${toString ports.public}";
      backendEndpoint = "127.0.0.1:${toString ports.backend}";
      proxy = "${name}-proxy";
      waitForBackend = pkgs.writeShellApplication {
        name = "${proxy}-wait-backend";
        runtimeInputs = [ pkgs.coreutils ];
        text = ''
          deadline=$((SECONDS + ${toString readinessTimeout}))
          until (exec 3<>"/dev/tcp/127.0.0.1/${toString ports.backend}") 2>/dev/null; do
            if [ "$SECONDS" -ge "$deadline" ]; then
              echo "${proxy}: timed out after ${toString readinessTimeout}s waiting for ${backendUnit} to listen on ${backendEndpoint}" >&2
              exit 1
            fi
            sleep 0.2
          done
        '';
      };
    in
    {
      inherit proxy backendUnit gpuExclusive;
      socket = {
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
      service = {
        description = "Idle-aware socket proxy for ${backendUnit}";
        requires = [ backendUnit ];
        after = [ backendUnit ];
        serviceConfig = {
          ExecStartPre = "${waitForBackend}/bin/${proxy}-wait-backend";
          ExecStart = "${systemdSocketProxyd} --exit-idle-time=${idleTimeout} ${backendEndpoint}";
          Restart = "no";
        };
      };
      runtimeSurface = {
        unit = "${proxy}.socket";
        kind = "socket";
        resourceClass = "interactive-agent";
        activation = {
          mode = "socket-proxy";
          inherit
            publicEndpoint
            backendEndpoint
            idleTimeout
            readinessTimeout
            ;
          exclusiveResource = if gpuExclusive then "gpu-inference" else null;
          dependsOn = [ name ];
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };
    };

  # One row per socket-activated backend, keyed by its `sinnix.services.<name>`
  # option and its runtime-surface name. Everything the front door needs -- the
  # socket, the proxy unit, the proxy's runtime surface, and membership in the
  # GPU exclusivity mesh -- is rendered from this table, so a backend cannot be
  # admitted to one of those and forgotten in another.
  #
  # `gpuExclusive` is the admission key: a member holds the card alone while
  # resident. CPU-only or CPU-pinned backends (stt, kokoro, litellm, llama-cpp)
  # are deliberately outside it and coexist with a resident model.
  proxySpecs = {
    ollama = {
      backendUnit = "ollama.service";
      ports = helpers.data.ports.ollama;
      # ~10x the cold-start cost of the daily-driver model (~20-23s); idling
      # out is cheaper than a wasted reload.
      idleTimeout = "240s";
      # Ollama is largely exempt from the cold-start-failure problem this probe
      # exists for: the daemon binds its port immediately and loads models
      # lazily per request. 30s is ample for the daemon itself.
      readinessTimeout = 30;
      gpuExclusive = true;
    };
    koboldcpp = {
      backendUnit = "koboldcpp.service";
      ports = helpers.data.ports.koboldcpp;
      # Unmeasurable: koboldcpp-cuda here fails CUDA init with `undefined
      # symbol: cuMemCreate` from koboldcpp_cublas.so on model load, so GPU
      # inference is non-functional regardless of timeout. Sized from its role
      # instead -- the deliberately-slow RAM-offloaded tier for GGUFs larger
      # than ollama's daily driver -- so at least as generous as ollama's 240s.
      idleTimeout = "300s";
      readinessTimeout = 300;
      gpuExclusive = true;
    };
    # Parakeet int8 through sherpa-onnx transcribes on the CPU fast enough that
    # speech-to-text never needs the GPU (measured on this host: RTF 0.113 on
    # dense speech, 0.002 over a VAD-gated ambient chunk), so unlike the
    # whisper.cpp service it replaces it stays out of the mesh and a
    # transcription can run while a model is resident. The always-on speech
    # lane is exactly the consumer that would otherwise have queued behind an
    # LLM. Cold start loads a 650MB encoder, ~2s; the idle window is long
    # because nothing scarce is being held.
    stt = {
      backendUnit = "sinnix-stt.service";
      ports = helpers.data.ports.stt;
      idleTimeout = "300s";
      readinessTimeout = 60;
    };
    litellm = {
      backendUnit = "litellm.service";
      ports = helpers.data.ports.litellm;
      # Lightweight gateway process, unmeasured; kept at the baseline default.
      idleTimeout = "30s";
      readinessTimeout = 30;
    };
    # Kokoro is CPU-only (modules/services/kokoro.nix) and must stay answerable
    # regardless of which CUDA backend, if any, currently holds the card.
    # Unmeasured; kept at the baseline default.
    kokoro = {
      backendUnit = "podman-kokoro.service";
      ports = helpers.data.ports.kokoro;
      idleTimeout = "30s";
      readinessTimeout = 30;
    };
    # The reranker runs CPU-pinned (gpuLayers = 0, hosts/sinnix-prime/default.nix).
    # It is not VRAM-free -- the CUDA-linked binary still allocates
    # ~680-740MiB even at -ngl 0 -- but far below the ~1610MiB it held fully
    # offloaded, so it stays out of the mesh and coexists with a resident
    # ollama/koboldcpp session. Cold /v1/rerank for the 0.6B reranker is ~1-3s;
    # 30s is ~10-30x headroom for both timeouts.
    llama-cpp = {
      backendUnit = "llama-cpp.service";
      ports = helpers.data.ports.llamaCpp;
      idleTimeout = "30s";
      readinessTimeout = 30;
    };
    muse-glimmer = {
      backendUnit = "muse-glimmer.service";
      ports = helpers.data.ports.museGlimmer;
      idleTimeout = "900s";
      readinessTimeout = 600;
      gpuExclusive = true;
    };
    # Strict full offload: the load either fits the card or fails, so the
    # readiness window matches muse-glimmer's rather than ollama's lazy one.
    qwen38-vram = {
      backendUnit = "qwen38-vram.service";
      ports = helpers.data.ports.qwen38Vram;
      idleTimeout = "900s";
      readinessTimeout = 600;
      gpuExclusive = true;
    };
    # ComfyUI, TTS (OpenedAI-Speech), MusicGen, and OCR are OCI containers with
    # CDI GPU passthrough (modules/services/{comfyui,tts,musicgen,ocr}.nix), but
    # `virtualisation.oci-containers` generates an ordinary
    # systemd.services.podman-<name> unit, so they proxy exactly like the native
    # backends. The one container-specific requirement: the container's own
    # `ports` mapping must sit on the backend port, leaving the public port to
    # systemd-socket-proxyd.
    #
    # ComfyUI cold start to a 200 from `/` is ~105s: the
    # mmartial/comfyui-nvidia-docker image re-resolves its Python venv on every
    # launch, re-downloading a ~930MB torch wheel, which dominates the cost
    # before any checkpoint loads. 900s idle because a real ComfyUI session
    # (queue a generation, wait on output) is a long round trip; 180s readiness
    # keeps a stuck container failing loud instead of hanging for the full idle
    # timeout.
    comfyui = {
      backendUnit = "podman-comfyui.service";
      ports = helpers.data.ports.comfyui;
      idleTimeout = "900s";
      readinessTimeout = 180;
      gpuExclusive = true;
    };
    # Cold start to a 200 from /v1/audio/speech (Piper voice) is ~17s; XTTS
    # voice cloning is heavier. 300s/60s covers headroom for both voices.
    tts = {
      backendUnit = "podman-openedai-speech.service";
      ports = helpers.data.ports.tts;
      idleTimeout = "300s";
      readinessTimeout = 60;
      gpuExclusive = true;
    };
    # Unmeasured (disabled on this host). Same all-in-one Gradio+PyTorch
    # toolkit shape as ComfyUI, so sized to the same tier.
    musicgen = {
      backendUnit = "podman-musicgen.service";
      ports = helpers.data.ports.musicgen;
      idleTimeout = "900s";
      readinessTimeout = 180;
      gpuExclusive = true;
    };
    # Unmeasured (disabled on this host). marker-api's Surya weights are small
    # (~1-2GB) next to ComfyUI's checkpoint tree, so sized to the tts container
    # tier.
    ocr = {
      backendUnit = "podman-ocr.service";
      ports = helpers.data.ports.ocr;
      idleTimeout = "300s";
      readinessTimeout = 60;
      gpuExclusive = true;
    };
  };

  proxies = lib.mapAttrs mkProxy proxySpecs;

  # Every rendered fragment is gated on its own backend's enable flag alone.
  forEachProxy =
    render:
    lib.mkMerge (
      lib.mapAttrsToList (name: p: lib.mkIf config.sinnix.services.${name}.enable (render p)) proxies
    );

  # ── GPU-inference exclusivity mesh ───────────────────────────────────────
  # Every `gpuExclusive` backend claims the GPU alone. Computing the pairwise
  # Conflicts= matrix from the one table keeps a newly admitted backend from
  # landing asymmetric. Each side's Conflicts= is gated on its OWN service's
  # enable flag only, never the peer's: a Conflicts= entry naming an undefined
  # unit is a harmless no-op in systemd, and cross-referencing peer enable state
  # would make a dozen modules' correctness depend on read-order.
  gpuMesh = lib.filterAttrs (_: p: p.gpuExclusive) proxies;
  gpuInferenceConflicts = lib.mkMerge (
    lib.mapAttrsToList (
      name: p:
      lib.mkIf config.sinnix.services.${name}.enable (
        let
          peerUnits = lib.concatMap (peer: [
            peer.backendUnit
            "${peer.proxy}.service"
          ]) (lib.attrValues (lib.filterAttrs (peerName: _: peerName != name) gpuMesh));
        in
        {
          ${lib.removeSuffix ".service" p.backendUnit}.conflicts = peerUnits;
          ${p.proxy}.conflicts = peerUnits;
        }
      )
    ) gpuMesh
  );
in
{
  environment.systemPackages = [ scriptPkgs.sinnix-ai ];
  systemd.sockets = forEachProxy (p: {
    ${p.proxy} = p.socket;
  });
  systemd.services = lib.mkMerge [
    (forEachProxy (p: {
      ${p.proxy} = p.service;
    }))
    gpuInferenceConflicts
  ];
  sinnix.runtime.surfaces = forEachProxy (p: {
    ${p.proxy} = p.runtimeSurface;
  });
}
