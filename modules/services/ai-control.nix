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
in
{
  environment.systemPackages = [ scriptPkgs.sinnix-ai ];
  systemd.sockets = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.sockets)
    (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.sockets)
    (lib.mkIf config.sinnix.services.whisper.enable whisperProxy.sockets)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.sockets)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.sockets)
  ];
  systemd.services = lib.mkMerge [
    (lib.mkIf config.sinnix.services.ollama.enable ollamaProxy.services)
    (lib.mkIf config.sinnix.services.koboldcpp.enable koboldcppProxy.services)
    (lib.mkIf config.sinnix.services.whisper.enable whisperProxy.services)
    (lib.mkIf config.sinnix.services.litellm.enable litellmProxy.services)
    (lib.mkIf config.sinnix.services.kokoro.enable kokoroProxy.services)
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
  ];
}
