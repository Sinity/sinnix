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

  mkProxy =
    {
      name,
      backendUnit,
      publicEndpoint,
      backendEndpoint,
      exclusiveResource ? null,
      dependsOn ? [ ],
      conflicts ? [ ],
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
        conflicts = conflicts;
        serviceConfig = {
          ExecStart = "${systemdSocketProxyd} --exit-idle-time=30s ${backendEndpoint}";
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
            ;
          idleTimeout = "30s";
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
    exclusiveResource = "gpu-inference";
    dependsOn = [ "ollama" ];
    conflicts = [
      "koboldcpp.service"
      "koboldcpp-proxy.service"
      "whisper-server.service"
      "whisper-proxy.service"
      "llama-cpp.service"
      "llama-cpp-proxy.service"
    ];
  };
  koboldcppProxy = mkProxy {
    name = "koboldcpp-proxy";
    backendUnit = "koboldcpp.service";
    publicEndpoint = "127.0.0.1:5001";
    backendEndpoint = "127.0.0.1:5002";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "koboldcpp" ];
    conflicts = [
      "ollama.service"
      "ollama-proxy.service"
      "whisper-server.service"
      "whisper-proxy.service"
      "llama-cpp.service"
      "llama-cpp-proxy.service"
    ];
  };
  whisperProxy = mkProxy {
    name = "whisper-proxy";
    backendUnit = "whisper-server.service";
    publicEndpoint = "127.0.0.1:8090";
    backendEndpoint = "127.0.0.1:8091";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "whisper" ];
    conflicts = [
      "ollama.service"
      "ollama-proxy.service"
      "koboldcpp.service"
      "koboldcpp-proxy.service"
      "llama-cpp.service"
      "llama-cpp-proxy.service"
    ];
  };
  llamaCppProxy = mkProxy {
    name = "llama-cpp-proxy";
    backendUnit = "llama-cpp.service";
    publicEndpoint = "127.0.0.1:8081";
    backendEndpoint = "127.0.0.1:8082";
    exclusiveResource = "gpu-inference";
    dependsOn = [ "llama-cpp" ];
    conflicts = [
      "ollama.service"
      "ollama-proxy.service"
      "koboldcpp.service"
      "koboldcpp-proxy.service"
      "whisper-server.service"
      "whisper-proxy.service"
    ];
  };
  litellmProxy = mkProxy {
    name = "litellm-proxy";
    backendUnit = "litellm.service";
    publicEndpoint = "127.0.0.1:4000";
    backendEndpoint = "127.0.0.1:4001";
    dependsOn = [ "ollama-proxy" ];
  };
  # Deliberately no exclusiveResource / conflicts here: Kokoro is CPU-only
  # (modules/services/kokoro.nix) and must stay answerable regardless of
  # which CUDA backend, if any, currently holds gpu-inference.
  kokoroProxy = mkProxy {
    name = "kokoro-proxy";
    backendUnit = "podman-kokoro.service";
    publicEndpoint = "127.0.0.1:8890";
    backendEndpoint = "127.0.0.1:8891";
  };

  # ComfyUI, TTS (OpenedAI-Speech), MusicGen, and OCR are OCI containers with
  # CDI GPU passthrough (modules/services/{comfyui,tts,musicgen,ocr}.nix)
  # rather than native systemd services with their own .service/.socket pair,
  # so they cannot join the mkProxy mesh above -- a container publishes its
  # port directly and podman start/stop has no idle-aware backend for
  # systemd-socket-proxyd to sit in front of. Forcing the socket-proxy shape
  # onto them would not fit; the closest correct admission control is a
  # mutual systemd Conflicts= against every native gpu-inference
  # service/proxy pair and every other GPU container, so systemd itself
  # refuses to run two resident at once -- the same hard guarantee the
  # socket-proxy mesh gives the native backends, minus proxy idle-teardown
  # (containers are all autoStart = false; sinnix-ai/the operator stops them
  # explicitly). This generalizes the exact gap the operator found for
  # llama-cpp (sinnix-w9l/e2fb0af) to the container lane (sinnix-joac).
  gpuContainerUnits = {
    comfyui = "podman-comfyui.service";
    tts = "podman-openedai-speech.service";
    musicgen = "podman-musicgen.service";
    ocr = "podman-ocr.service";
  };
  gpuNativeUnits = [
    "ollama.service"
    "ollama-proxy.service"
    "koboldcpp.service"
    "koboldcpp-proxy.service"
    "whisper-server.service"
    "whisper-proxy.service"
    "llama-cpp.service"
    "llama-cpp-proxy.service"
  ];
  # (sinnix.services enable option, systemd unit name minus ".service") for
  # every native gpu-inference unit -- both the backend and its proxy, since
  # each proxy already carries its own Conflicts= against every other
  # backend/proxy (the `conflicts` passed to mkProxy above) and would
  # otherwise stay silently exempt from the container side of the matrix.
  # whisper's option is "whisper" but its units are "whisper-server" /
  # "whisper-proxy"; everything else matches its option name.
  gpuNativeServiceUnits = [
    { service = "ollama"; unit = "ollama"; }
    { service = "ollama"; unit = "ollama-proxy"; }
    { service = "koboldcpp"; unit = "koboldcpp"; }
    { service = "koboldcpp"; unit = "koboldcpp-proxy"; }
    { service = "whisper"; unit = "whisper-server"; }
    { service = "whisper"; unit = "whisper-proxy"; }
    { service = "llama-cpp"; unit = "llama-cpp"; }
    { service = "llama-cpp"; unit = "llama-cpp-proxy"; }
  ];
  # Each side's Conflicts= addition is gated on its OWN service's enable
  # flag only (never the peer's), matching the existing convention in
  # ollama.nix/koboldcpp.nix/whisper.nix/llama-cpp.nix, which already list
  # every native peer unconditionally: a Conflicts= entry naming a unit that
  # never gets defined (peer disabled) is a harmless no-op in systemd, not
  # an error, so there is nothing to gain by cross-referencing peer enable
  # state and doing so would just make four more modules' correctness depend
  # on read-order.
  containerGpuConflicts = lib.mapAttrsToList (
    serviceName: unit:
    lib.mkIf config.sinnix.services.${serviceName}.enable {
      ${lib.removeSuffix ".service" unit}.conflicts =
        gpuNativeUnits ++ (lib.remove unit (lib.attrValues gpuContainerUnits));
    }
  ) gpuContainerUnits;
  nativeGpuContainerConflicts = map (
    { service, unit }:
    lib.mkIf config.sinnix.services.${service}.enable {
      ${unit}.conflicts = lib.attrValues gpuContainerUnits;
    }
  ) gpuNativeServiceUnits;
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
  ];
  systemd.services = lib.mkMerge (
    [
      (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.services)
      (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.services)
      (lib.mkIf config.sinnix.services.whisper.enable whisperProxy.services)
      (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.services)
      (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.services)
      (lib.mkIf config.sinnix.services.llama-cpp.enable llamaCppProxy.services)
    ]
    ++ containerGpuConflicts
    ++ nativeGpuContainerConflicts
  );
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
  ];
}
