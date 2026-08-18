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
  helpers,
  ...
}@args:
mkServiceModule {
  name = "koboldcpp";
  description = "koboldcpp all-in-one inference (CUDA)";
  docs = "docs/local-ai-activation.md";
  surface = {
    unit = "koboldcpp.service";
    resourceClass = "interactive-agent";
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:${toString helpers.data.ports.koboldcpp.public}";
      backendEndpoint = "127.0.0.1:${toString helpers.data.ports.koboldcpp.backend}";
      idleTimeout = "300s";
      exclusiveResource = "gpu-inference";
      dependsOn = [ "koboldcpp-proxy" ];
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
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      modelRoot = "${config.sinnix.paths.modelsRoot}";
      args' = lib.concatStringsSep " " (
        [
          "${pkgs.koboldcpp-cuda}/bin/koboldcpp"
          "--host 127.0.0.1"
          "--port ${toString helpers.data.ports.koboldcpp.backend}"
          "--usecublas normal"
          "--gpulayers ${toString cfg.gpuLayers}"
          "--quiet"
          # There is no $DISPLAY under systemd, ever. Without this, koboldcpp
          # with no --model tries its Tk file-picker GUI and dies on
          # Tk_Init error -- exactly what a socket-activation probe with no
          # model configured hits (2026-08-18: a stray connection to the
          # public port triggered this and crash-looped every 10s). The
          # built-in web UI (KoboldAI Lite, :5001) is unaffected.
          "--skiplauncher"
        ]
        # --skiplauncher above only suppresses the launcher-config GUI; with
        # no --model AND no --skiplauncher-covered fallback, koboldcpp falls
        # into a SEPARATE tkinter askopenfilename "pick a model" dialog
        # (verified live 2026-08-18: py-spy caught the process blocked in
        # show_gui -> zentk_askopenfilename while --skiplauncher alone let it
        # sail past the launcher and straight into that picker). --nomodel is
        # the flag that actually means "run without one, don't ask".
        ++ lib.optional (cfg.model == "") "--nomodel"
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
        partOf = [ "koboldcpp-proxy.service" ];
        # Conflicts= against every other GPU-inference backend is computed
        # centrally in ai-control.nix's gpuInferenceConflicts.
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
