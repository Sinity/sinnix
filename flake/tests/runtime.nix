# Runtime inventory schema checks for typed effective per-surface policy.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) evalTestSpec mkFeatureTest;
      spec = mkFeatureTest {
        name = "runtime-surface-policy";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          ({ ... }: {
            sinnix.runtime.surfaces = {
              runtime-policy-system = {
                unit = "runtime-policy-system.service";
                resourceClass = "background-maintenance";
                resources = {
                  MemoryMax = "900M";
                  Nice = 7;
                };
                observe.enable = true;
              };
              runtime-policy-user = {
                unit = "runtime-policy-user.service";
                manager = "user";
                resourceClass = "desktop-shell";
                resources = {
                  MemoryLow = "768M";
                };
                observe.enable = true;
              };
            };
            systemd.services.runtime-policy-system = { };
            home-manager.users.sinity.systemd.user.services.runtime-policy-user = { };
          })
        ];
        assertions = config: [
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-system.effectiveResources.MemoryMax
              == "900M";
            message = "system surface overrides must appear in effective runtime policy";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-system.effectiveResources.Nice == 7;
            message = "system surface Nice override must be preserved";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-user.effectiveResources.MemoryLow == "768M";
            message = "user surface overrides must appear in effective runtime policy";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.runtime-policy-user.effectiveResources.CPUWeight == 400;
            message = "resource-class defaults must remain under user overrides";
          }
          {
            assertion =
              config.systemd.services.runtime-policy-system.unitConfig.OnFailure
              == [ "sinnix-health-transition@%n" ];
            message = "observed system services must receive the system health transition template";
          }
          {
            # Delivered as a drop-in rather than a unit body: a user surface
            # may be declared through home-manager or through the NixOS-level
            # systemd.user.services, and only a drop-in merges with both.
            assertion =
              config.home-manager.users.sinity.xdg.configFile
              ? "systemd/user/runtime-policy-user.service.d/50-sinnix-health-transition.conf";
            message = "observed user services must receive the user health transition drop-in";
          }
        ];
      };
      evaluated = evalTestSpec system spec;
      inventoryJson = builtins.toJSON evaluated.config.sinnix.runtime.inventory;
      localModels = import ../data/local-models.nix { inherit lib; };
      localModelRosterJson = builtins.toJSON {
        models = localModels.models;
        inherit (localModels) ollamaLoadModels litellmModelList;
      };
      aiActivationSpec = mkFeatureTest {
        name = "ai-activation";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          ({ ... }: {
            sinnix.services.ollama.enable = true;
            sinnix.services.koboldcpp.enable = true;
            sinnix.services.litellm.enable = true;
            sinnix.services.open-webui.enable = true;
            sinnix.services.stt.enable = true;
            sinnix.services.tts.enable = true;
            sinnix.services.llama-cpp.enable = true;
            sinnix.services.muse-glimmer.enable = true;
            sinnix.services.comfyui.enable = true;
            sinnix.services.musicgen.enable = true;
            sinnix.services.ocr.enable = true;
          })
        ];
        assertions =
          config:
          let
            # Every socket-proxy surface, read from the inventory rather than
            # listed here, so a new backend is covered the day it is declared.
            proxySurfaces = lib.filterAttrs (
              _: surface:
              (surface.activation.mode or "direct") == "socket-proxy" && (surface.kind or "service") == "socket"
            ) config.sinnix.runtime.inventory.surfaces;
            proxyNames = map (lib.removeSuffix ".socket") (
              lib.mapAttrsToList (_: surface: surface.unit) proxySurfaces
            );
            backendUnitsOf =
              proxyName:
              lib.filter (unit: lib.elem "${proxyName}.service" (config.systemd.services.${unit}.partOf or [ ])) (
                lib.attrNames config.systemd.services
              );
          in
          [
            {
              # The defect that killed muse-glimmer's front door on
              # 2026-08-16: a backend carrying BindsTo= (or Requires=) on its
              # proxy makes ANY backend start pull the proxy in outside socket
              # activation, where systemd-socket-proxyd has no listen fds,
              # exits 1, and -- via that same edge -- takes the backend down
              # with it. PartOf= alone gives the idle teardown with no start
              # dependency, so the edge must never point back up.
              assertion = builtins.all (
                proxyName:
                builtins.all (
                  backend:
                  !(lib.elem "${proxyName}.service" (config.systemd.services.${backend}.bindsTo or [ ]))
                  && !(lib.elem "${proxyName}.service" (config.systemd.services.${backend}.requires or [ ]))
                ) (backendUnitsOf proxyName)
              ) proxyNames;
              message = "A socket-proxy backend must not declare BindsTo=/Requires= on its own proxy: that starts the proxy without socket activation and cascades its failure back into the backend";
            }
            {
              # Without an explicit limit the default is 200 activations in
              # 2s, which a client retrying through a cold model load can
              # spend in one burst -- after which systemd latches the socket
              # into failed permanently and the public port refuses
              # everything.
              assertion = builtins.all (
                proxyName:
                (config.systemd.sockets.${proxyName}.socketConfig.TriggerLimitBurst or null) != null
                && (config.systemd.sockets.${proxyName}.socketConfig.TriggerLimitIntervalSec or null) != null
              ) proxyNames;
              message = "Every socket-proxy front door must set an explicit activation trigger limit rather than inheriting systemd's short default window";
            }
            {
              assertion = config.systemd.sockets.ollama-proxy.listenStreams == [ "127.0.0.1:11434" ];
              message = "Ollama must expose only its socket-activated loopback front door";
            }
            {
              assertion = config.systemd.services.ollama.partOf == [ "ollama-proxy.service" ];
              message = "Stopping an idle Ollama proxy must stop its backend";
            }
            {
              assertion = lib.hasInfix "systemd-socket-proxyd" config.systemd.services.ollama-proxy.serviceConfig.ExecStart;
              message = "Ollama activation must use the systemd socket proxy";
            }
            {
              assertion = lib.hasInfix "--exit-idle-time=30s" config.systemd.services.ollama-proxy.serviceConfig.ExecStart;
              message = "AI activation must have a bounded idle timeout";
            }
            {
              assertion =
                lib.elem "ollama.service" config.systemd.services.koboldcpp.unitConfig.Conflicts
                && lib.elem "koboldcpp.service" config.systemd.services.ollama.unitConfig.Conflicts;
              message = "GPU inference backends must be mutually exclusive";
            }
            {
              assertion =
                config.sinnix.runtime.inventory.surfaces.ollama.activation.backendEndpoint == "127.0.0.1:11435"
                &&
                  config.sinnix.runtime.inventory.surfaces.ollama-proxy.activation.publicEndpoint
                  == "127.0.0.1:11434";
              message = "Runtime inventory must describe the public and private AI activation endpoints";
            }
            {
              assertion =
                config.sinnix.runtime.inventory.surfaces.litellm.activation.dependsOn == [ "ollama-proxy" ];
              message = "LiteLLM activation must retain the Ollama socket dependency";
            }
            {
              assertion =
                config.sinnix.runtime.inventory.surfaces.open-webui.activation.publicEndpoint == "127.0.0.1:8080"
                && config.sinnix.runtime.inventory.surfaces.tts.activation.publicEndpoint == "127.0.0.1:8000";
              message = "The AI factory must preserve direct loopback endpoints for representative services";
            }
            {
              assertion =
                config.systemd.services.sinnix-stt.serviceConfig.ExecStart != null
                && lib.hasInfix "sinnix-stt" config.systemd.services.sinnix-stt.serviceConfig.ExecStart;
              message = "The AI factory must leave the native STT command visible";
            }
            {
              assertion = config.systemd.sockets.stt-proxy.listenStreams == [ "127.0.0.1:8090" ];
              message = "The STT hub must expose only its socket-activated loopback front door";
            }
            {
              assertion = config.systemd.services.sinnix-stt.partOf == [ "stt-proxy.service" ];
              message = "An idle stt-proxy exit must tear down the STT backend cgroup";
            }
            {
              assertion = lib.hasInfix "systemd-socket-proxyd" config.systemd.services.stt-proxy.serviceConfig.ExecStart;
              message = "STT activation must use the idle-aware systemd socket proxy";
            }
            {
              assertion =
                config.sinnix.runtime.inventory.surfaces.stt.activation.backendEndpoint == "127.0.0.1:8091"
                && config.sinnix.runtime.inventory.surfaces.stt-proxy.activation.publicEndpoint == "127.0.0.1:8090";
              message = "Runtime inventory must describe the public and private STT activation endpoints";
            }
            {
              # The inverse of the assertion this replaces, and it is the point
              # of the engine change rather than an omission: Parakeet runs on
              # the CPU, so speech-to-text must NOT hold the gpu-inference key
              # and must stay available while a model is resident.
              assertion =
                !(lib.elem "sinnix-stt.service" config.systemd.services.ollama.unitConfig.Conflicts)
                && !(lib.elem "sinnix-stt.service" config.systemd.services.koboldcpp.unitConfig.Conflicts);
              message = "The CPU-only STT hub must stay outside the gpu-inference admission mesh";
            }
            {
              assertion =
                config.systemd.services.podman-openedai-speech.serviceConfig.ExecStart != null
                && lib.hasInfix "podman" config.systemd.services.podman-openedai-speech.serviceConfig.ExecStart;
              message = "The AI factory must leave the container launch visible";
            }
            {
              assertion = config.systemd.sockets.llama-cpp-proxy.listenStreams == [ "127.0.0.1:8081" ];
              message = "llama-cpp must expose only its socket-activated loopback front door";
            }
            {
              assertion =
                config.systemd.sockets.muse-glimmer-proxy.listenStreams == [ "127.0.0.1:8083" ]
                &&
                  config.sinnix.runtime.inventory.surfaces.muse-glimmer-proxy.activation.backendEndpoint
                  == "127.0.0.1:8084";
              message = "Muse Glimmer must expose its dedicated socket-activated loopback endpoint";
            }
            {
              assertion =
                lib.hasInfix "--fit-target 1536" config.systemd.services.muse-glimmer.serviceConfig.ExecStart
                && lib.hasInfix "--ctx-size 32768" config.systemd.services.muse-glimmer.serviceConfig.ExecStart
                && lib.hasInfix "--parallel 1" config.systemd.services.muse-glimmer.serviceConfig.ExecStart;
              message = "Muse Glimmer must retain the bounded hybrid inference profile";
            }
            {
              assertion = config.systemd.services.llama-cpp.partOf == [ "llama-cpp-proxy.service" ];
              message = "An idle llama-cpp-proxy exit must tear down the llama-cpp backend cgroup";
            }
            {
              assertion =
                lib.hasInfix "systemd-socket-proxyd" config.systemd.services.llama-cpp-proxy.serviceConfig.ExecStart
                && lib.hasInfix "--exit-idle-time=30s" config.systemd.services.llama-cpp-proxy.serviceConfig.ExecStart;
              message = "llama-cpp activation must use the idle-aware systemd socket proxy";
            }
            {
              assertion =
                config.sinnix.runtime.inventory.surfaces.llama-cpp.activation.backendEndpoint == "127.0.0.1:8082"
                &&
                  config.sinnix.runtime.inventory.surfaces.llama-cpp-proxy.activation.publicEndpoint
                  == "127.0.0.1:8081";
              message = "Runtime inventory must describe the public and private llama-cpp activation endpoints";
            }
            {
              # Cold start: the proxy must not
              # start forwarding until the backend's port actually accepts a
              # connection, or the client's parked request gets a hard refusal
              # during the weight-load window instead of a queue.
              assertion =
                lib.hasInfix "wait-backend" config.systemd.services.llama-cpp-proxy.serviceConfig.ExecStartPre
                && config.sinnix.runtime.inventory.surfaces.llama-cpp-proxy.activation.readinessTimeout == 30;
              message = "llama-cpp-proxy must gate its socket proxy on backend readiness before forwarding";
            }
            {
              assertion =
                lib.hasInfix "wait-backend" config.systemd.services.comfyui-proxy.serviceConfig.ExecStartPre
                && config.sinnix.runtime.inventory.surfaces.comfyui-proxy.activation.readinessTimeout == 180;
              message = "comfyui-proxy must gate its socket proxy on backend readiness before forwarding, with a bound matching its measured cold-start cost";
            }
            {
              assertion = config.systemd.sockets.comfyui-proxy.listenStreams == [ "127.0.0.1:8188" ];
              message = "ComfyUI must expose only its socket-activated loopback front door";
            }
            {
              assertion =
                config.systemd.services.podman-comfyui.unitConfig.PartOf == [ "comfyui-proxy.service" ]
                && config.systemd.services.podman-comfyui.unitConfig.BindsTo == [ "comfyui-proxy.service" ];
              message = "An idle comfyui-proxy exit must tear down the ComfyUI container cgroup";
            }
            {
              assertion =
                lib.hasInfix "systemd-socket-proxyd" config.systemd.services.comfyui-proxy.serviceConfig.ExecStart
                && lib.hasInfix "--exit-idle-time=900s" config.systemd.services.comfyui-proxy.serviceConfig.ExecStart;
              message = "ComfyUI activation must use the idle-aware systemd socket proxy with its measured, generous timeout";
            }
            {
              assertion = config.systemd.sockets.tts-proxy.listenStreams == [ "127.0.0.1:8000" ];
              message = "TTS must expose only its socket-activated loopback front door";
            }
            {
              assertion =
                config.systemd.services.podman-openedai-speech.unitConfig.PartOf == [ "tts-proxy.service" ]
                && config.systemd.services.podman-openedai-speech.unitConfig.BindsTo == [ "tts-proxy.service" ];
              message = "An idle tts-proxy exit must tear down the TTS container cgroup";
            }
            {
              assertion = config.systemd.sockets.musicgen-proxy.listenStreams == [ "127.0.0.1:8010" ];
              message = "MusicGen must expose only its socket-activated loopback front door";
            }
            {
              assertion =
                config.systemd.services.podman-musicgen.unitConfig.PartOf == [ "musicgen-proxy.service" ]
                && config.systemd.services.podman-musicgen.unitConfig.BindsTo == [ "musicgen-proxy.service" ];
              message = "An idle musicgen-proxy exit must tear down the MusicGen container cgroup";
            }
            {
              assertion = config.systemd.sockets.ocr-proxy.listenStreams == [ "127.0.0.1:8020" ];
              message = "OCR must expose only its socket-activated loopback front door";
            }
            {
              assertion =
                config.systemd.services.podman-ocr.unitConfig.PartOf == [ "ocr-proxy.service" ]
                && config.systemd.services.podman-ocr.unitConfig.BindsTo == [ "ocr-proxy.service" ];
              message = "An idle ocr-proxy exit must tear down the OCR container cgroup";
            }
            {
              # Full symmetry across all seven GPU-inference backends (three
              # native, four containerized): every (service, proxy) pair must
              # conflict with every other backend's (service, proxy) pair in
              # both directions. An asymmetric conflict set is exactly the bug
              # this check exists to catch. llama-cpp is intentionally NOT a
              # member (CPU-pinned reranker, checked separately below) -- it
              # must not appear in this map.
              assertion =
                let
                  backendUnits = {
                    ollama = [
                      "ollama.service"
                      "ollama-proxy.service"
                    ];
                    koboldcpp = [
                      "koboldcpp.service"
                      "koboldcpp-proxy.service"
                    ];
                    comfyui = [
                      "podman-comfyui.service"
                      "comfyui-proxy.service"
                    ];
                    tts = [
                      "podman-openedai-speech.service"
                      "tts-proxy.service"
                    ];
                    musicgen = [
                      "podman-musicgen.service"
                      "musicgen-proxy.service"
                    ];
                    ocr = [
                      "podman-ocr.service"
                      "ocr-proxy.service"
                    ];
                    muse-glimmer = [
                      "muse-glimmer.service"
                      "muse-glimmer-proxy.service"
                    ];
                  };
                  unitConflicts =
                    unit: config.systemd.services.${lib.removeSuffix ".service" unit}.unitConfig.Conflicts;
                  allSymmetric = lib.all (
                    backendA:
                    lib.all (
                      backendB:
                      backendA == backendB
                      || lib.all (
                        unitA:
                        lib.all (
                          unitB: lib.elem unitB (unitConflicts unitA) && lib.elem unitA (unitConflicts unitB)
                        ) backendUnits.${backendB}
                      ) backendUnits.${backendA}
                    ) (lib.attrNames backendUnits)
                  ) (lib.attrNames backendUnits);
                in
                allSymmetric;
              message = "Every remaining GPU-inference backend's service and proxy units must conflict symmetrically with every other backend's";
            }
            {
              # The reranker's deliberate exemption from the mesh, checked
              # directly rather than trusted by omission: it must not appear
              # in any GPU-large backend's Conflicts=, and it must not
              # conflict with any of them either.
              assertion =
                let
                  gpuLargeUnits = [
                    "ollama.service"
                    "ollama-proxy.service"
                    "koboldcpp.service"
                    "koboldcpp-proxy.service"
                    "podman-comfyui.service"
                    "comfyui-proxy.service"
                    "podman-openedai-speech.service"
                    "tts-proxy.service"
                    "podman-musicgen.service"
                    "musicgen-proxy.service"
                    "podman-ocr.service"
                    "ocr-proxy.service"
                    "muse-glimmer.service"
                    "muse-glimmer-proxy.service"
                  ];
                  unitConflicts =
                    unit: config.systemd.services.${lib.removeSuffix ".service" unit}.unitConfig.Conflicts or [ ];
                in
                lib.all (
                  unit:
                  !(lib.elem "llama-cpp.service" (unitConflicts unit))
                  && !(lib.elem "llama-cpp-proxy.service" (unitConflicts unit))
                ) gpuLargeUnits
                && (unitConflicts "llama-cpp") == [ ]
                && (unitConflicts "llama-cpp-proxy") == [ ];
              message = "llama-cpp (CPU-pinned reranker) must be absent from the gpu-inference conflicts mesh in both directions";
            }
          ];
      };
      aiActivationEvaluated = evalTestSpec system aiActivationSpec;
      groupSpec = mkFeatureTest {
        name = "hyprland-groups";
        feature = "sinnix.features.desktop.hyprland.enable";
        assertions = _: [ ];
      };
      groupEvaluated = evalTestSpec system groupSpec;
      groupBindingsJson =
        let
          hyprSettings =
            groupEvaluated.config.home-manager.users.sinity.wayland.windowManager.hyprland.settings;
        in
        builtins.toJSON (
          # Every bind family the module emits. These are the described
          # variants (bindd/binddl/binddm) -- see hyprland/bindings.nix. A
          # chord collision across families shadows just as silently as one
          # within a family, so check them together.
          (hyprSettings.bindd or [ ]) ++ (hyprSettings.binddl or [ ]) ++ (hyprSettings.binddm or [ ])
        );
    in
    {
      checks.runtime-surface-policy =
        pkgs.runCommand "runtime-surface-policy-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > inventory.json <<'EOF_INVENTORY'
            ${inventoryJson}
            EOF_INVENTORY
            jq -e '.surfaces["runtime-policy-system"].effectiveResources.MemoryMax == "900M" and .surfaces["runtime-policy-user"].effectiveResources.MemoryLow == "768M"' inventory.json >/dev/null
            touch "$out"
          '';
      checks.ai-activation =
        pkgs.runCommand "ai-activation-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > inventory.json <<'EOF_INVENTORY'
            ${builtins.toJSON aiActivationEvaluated.config.sinnix.runtime.inventory}
            EOF_INVENTORY
            jq -e '
              .surfaces.ollama.activation.mode == "socket-proxy" and
              .surfaces.ollama.activation.backendEndpoint == "127.0.0.1:11435" and
              .surfaces["ollama-proxy"].activation.publicEndpoint == "127.0.0.1:11434" and
              .surfaces["koboldcpp-proxy"].activation.exclusiveResource == "gpu-inference" and
              .surfaces.litellm.activation.dependsOn == ["ollama-proxy"] and
              .surfaces["llama-cpp"].activation.mode == "socket-proxy" and
              .surfaces["llama-cpp"].activation.backendEndpoint == "127.0.0.1:8082" and
              .surfaces["llama-cpp-proxy"].activation.publicEndpoint == "127.0.0.1:8081" and
              .surfaces["llama-cpp-proxy"].activation.exclusiveResource == null and
              .surfaces.comfyui.activation.mode == "socket-proxy" and
              .surfaces.comfyui.activation.backendEndpoint == "127.0.0.1:8189" and
              .surfaces["comfyui-proxy"].activation.publicEndpoint == "127.0.0.1:8188" and
              .surfaces["comfyui-proxy"].activation.idleTimeout == "900s" and
              .surfaces.tts.activation.mode == "socket-proxy" and
              .surfaces.tts.activation.backendEndpoint == "127.0.0.1:8001" and
              .surfaces["tts-proxy"].activation.publicEndpoint == "127.0.0.1:8000" and
              .surfaces.musicgen.activation.mode == "socket-proxy" and
              .surfaces["musicgen-proxy"].activation.publicEndpoint == "127.0.0.1:8010" and
              .surfaces.ocr.activation.mode == "socket-proxy" and
              .surfaces["ocr-proxy"].activation.publicEndpoint == "127.0.0.1:8020"
            ' inventory.json >/dev/null
            touch "$out"
          '';
      checks.local-model-roster =
        pkgs.runCommand "local-model-roster-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > roster.json <<'EOF_ROSTER'
            ${localModelRosterJson}
            EOF_ROSTER
            jq -e '
              any(.models[]; .ollamaTag == null and .litellmName == "local-glimmer" and .role == "general-reasoning-hybrid-dense") and
              (any(.ollamaLoadModels[]; . == "muse-glimmer") | not) and
              any(.litellmModelList[]; .model_name == "local-glimmer" and .litellm_params.model == "openai/muse-glimmer" and .litellm_params.api_base == "http://127.0.0.1:8083/v1")
            ' roster.json >/dev/null
            touch "$out"
          '';
      checks.hyprland-groups =
        pkgs.runCommand "hyprland-groups-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > bindings.json <<'EOF_BINDINGS'
            ${groupBindingsJson}
            EOF_BINDINGS
            # The one real invariant here: no two bindings may claim the same
            # chord (a duplicate silently shadows its twin). Which chords do
            # what is config content, not contract -- asserting exact binding
            # strings just memorializes the keymap diff-by-diff.
            jq -e '
              (map(split(",") | {chord: ((.[0] | gsub("^[[:space:]]+|[[:space:]]+$"; "")) + "," + (.[1] | gsub("^[[:space:]]+|[[:space:]]+$"; "")))})
                | group_by(.chord) | map(select(length > 1)) | length) == 0
            ' bindings.json >/dev/null
            touch "$out"
          '';
    };
}
