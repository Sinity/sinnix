# Muse Glimmer 30B direct llama.cpp endpoint.
#
# This is separate from the reranker service in llama-cpp.nix and from Ollama:
# the current Ollama package cannot load Glimmer's architecture. The official
# Q4 GGUF is deliberately hybrid-offloaded through llama.cpp, with fit margins
# that leave the desktop usable on the 10 GB RTX 3080.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "muse-glimmer";
  description = "Muse Glimmer 30B hybrid llama.cpp inference";
  surface = {
    unit = "muse-glimmer.service";
    resourceClass = "interactive-agent";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:8083";
      backendEndpoint = "127.0.0.1:8084";
      idleTimeout = "900s";
      readinessTimeout = 600;
      exclusiveResource = "gpu-inference";
      dependsOn = [ "muse-glimmer-proxy" ];
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    model = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "Glimmer GGUF filename under model/gguf to load at start.";
    };
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
      modelRoot = "${config.sinnix.paths.mediaRoot}/model";
      args' = lib.escapeShellArgs [
        "${pkgs.llama-cpp-cuda}/bin/llama-server"
        "--model"
        "${modelRoot}/gguf/${cfg.model}"
        "--host"
        "127.0.0.1"
        "--port"
        "8084"
        "--n-gpu-layers"
        "auto"
        "--fit"
        "on"
        "--fit-target"
        "1536"
        "--ctx-size"
        "32768"
        "--parallel"
        "1"
        "--flash-attn"
        "on"
        "--no-mmproj"
        "--jinja"
        "--chat-template-kwargs"
        ''{"reasoning_strength":"medium"}''
        "--temp"
        "1.0"
        "--top-p"
        "0.95"
        "--top-k"
        "64"
      ];
    in
    {
      systemd.tmpfiles.rules = [
        "d ${modelRoot}/gguf 0755 ${user} users -"
      ];

      systemd.services.muse-glimmer = {
        description = "Muse Glimmer 30B llama.cpp server";
        wantedBy = [ ];
        after = [ "network.target" ];
        partOf = [ "muse-glimmer-proxy.service" ];
        bindsTo = [ "muse-glimmer-proxy.service" ];
        serviceConfig = lib.mkMerge [
          {
            User = user;
            Group = "users";
            SupplementaryGroups = [
              "video"
              "render"
            ];
            ExecStart = args';
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "muse-glimmer.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 30;
          })
        ];
      };
    };
} args
