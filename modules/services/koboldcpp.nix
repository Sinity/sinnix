# koboldcpp — all-in-one CUDA inference (LLM/VLM + Stable Diffusion text-to-image).
#
# Single binary with a built-in web UI (KoboldAI Lite) on 127.0.0.1:5001 plus
# OpenAI- and A1111-compatible APIs. This is the Tier-2 vehicle for:
#   - deliberately-slow RAM-offloaded GGUF runs (--gpulayers spills to RAM),
#   - native Stable Diffusion image gen without containers,
#   - applying steering / control vectors (--control-vector) from the interp lab.
#
# On-demand (wantedBy = [ ]): start manually after placing a GGUF, so it never
# fails the boot transaction and never holds VRAM while idle.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "koboldcpp";
  description = "koboldcpp all-in-one inference (CUDA)";
  surface = {
    unit = "koboldcpp.service";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    model = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "GGUF text/vision model filename under model/gguf to load at start (empty = none).";
    };
    sdmodel = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "Stable Diffusion checkpoint filename under model/sd-checkpoints for image gen (empty = none).";
    };
    gpuLayers = args.lib.mkOption {
      type = args.lib.types.int;
      default = 999;
      description = "Layers offloaded to GPU; remainder spills to RAM. 999 = offload as many as fit.";
    };
    controlVector = args.lib.mkOption {
      type = args.lib.types.str;
      default = "";
      description = "Control-vector GGUF filename under model/control-vectors to apply (empty = none).";
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
      modelRoot = "${config.sinnix.paths.librariesRoot}/model";
      args' = lib.concatStringsSep " " (
        [
          "${pkgs.koboldcpp-cuda}/bin/koboldcpp"
          "--host 127.0.0.1"
          "--port 5001"
          "--usecublas normal"
          "--gpulayers ${toString cfg.gpuLayers}"
          "--quiet"
        ]
        ++ lib.optional (cfg.model != "") "--model ${modelRoot}/gguf/${cfg.model}"
        ++ lib.optional (cfg.sdmodel != "") "--sdmodel ${modelRoot}/sd-checkpoints/${cfg.sdmodel}"
        ++ lib.optional (
          cfg.controlVector != ""
        ) "--control-vector ${modelRoot}/control-vectors/${cfg.controlVector}"
      );
    in
    {
      systemd.tmpfiles.rules = [
        "d ${modelRoot}/gguf 0755 ${user} users -"
        "d ${modelRoot}/sd-checkpoints 0755 ${user} users -"
        "d ${modelRoot}/control-vectors 0755 ${user} users -"
      ];

      systemd.services.koboldcpp = {
        description = "koboldcpp all-in-one inference server";
        wantedBy = [ ]; # on-demand
        after = [ "network.target" ];
        serviceConfig = lib.mkMerge [
          {
            User = user;
            Group = "users";
            # GPU nodes are world-accessible on NixOS; keep groups for safety.
            SupplementaryGroups = [
              "video"
              "render"
            ];
            ExecStart = args';
          }
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "koboldcpp.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 10;
          })
        ];
      };
    };
} args
