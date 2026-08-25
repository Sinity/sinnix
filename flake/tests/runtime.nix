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
          (
            { mkServiceModule, ... }:
            {
              imports = [
                (mkServiceModule {
                  name = "failure-attach-plain";
                  description = "Generated job whose surface is not observed";
                  surface = {
                    unit = "sinnix-failure-attach-plain.service";
                    resourceClass = "background-maintenance";
                  };
                  job.execStart = "/bin/true";
                })
                (mkServiceModule {
                  name = "failure-attach-observed";
                  description = "Generated job whose surface is observed";
                  surface = {
                    unit = "sinnix-failure-attach-observed.service";
                    resourceClass = "background-maintenance";
                    observe.enable = true;
                  };
                  job.execStart = "/bin/true";
                })
              ];
              sinnix.services.failure-attach-plain.enable = true;
              sinnix.services.failure-attach-observed.enable = true;
            }
          )
        ];
        # Provably fails when: a surface's `resources` override stops
        # overriding its resource class, a class default stops merging in
        # under an override, or an observed surface loses its
        # failure-notify attachment.
        assertions =
          config:
          let
            surfaces = config.sinnix.runtime.inventory.surfaces;
            # The class table is the source of the defaults, so read the
            # expected values from it rather than restating them here.
            backgroundClass =
              (import ../data/runtime-defaults.nix { inherit lib; }).classes.background-maintenance.serviceConfig;
          in
          [
            {
              # Both fixture surfaces override a key their class also sets
              # (MemoryMax 3G, Nice 10) -- the override must win.
              assertion =
                surfaces.runtime-policy-system.effectiveResources.MemoryMax == "900M"
                && surfaces.runtime-policy-system.effectiveResources.Nice == 7
                && backgroundClass.MemoryMax != "900M"
                && backgroundClass.Nice != 7;
              message = "a surface's own resources must override its resource class's defaults";
            }
            {
              # ...and the keys it did not name must survive from the class,
              # or an override silently narrows a unit's whole policy.
              assertion =
                surfaces.runtime-policy-system.effectiveResources.IOWeight == backgroundClass.IOWeight
                &&
                  surfaces.runtime-policy-system.effectiveResources.IOSchedulingClass
                  == backgroundClass.IOSchedulingClass
                && surfaces.runtime-policy-system.effectiveResources.MemoryHigh == backgroundClass.MemoryHigh;
              message = "resource-class defaults the surface did not override must survive into effective policy";
            }
            {
              assertion =
                surfaces.runtime-policy-user.effectiveResources.MemoryLow == "768M"
                && surfaces.runtime-policy-user.effectiveResources.Slice == "desktop-shell.slice";
              message = "a user surface must keep its class slice placement alongside its own overrides";
            }
            {
              assertion =
                config.systemd.services.runtime-policy-system.unitConfig.OnFailure
                == [ "sinnix-unit-failure-notify@%n.service" ];
              message = "observed system services must receive the system failure-notify template";
            }
            {
              # Delivered as a drop-in rather than a unit body: a user surface
              # may be declared through home-manager or through the NixOS-level
              # systemd.user.services, and only a drop-in merges with both.
              assertion =
                config.home-manager.users.sinity.xdg.configFile
                ? "systemd/user/runtime-policy-user.service.d/50-sinnix-unit-failure-notify.conf";
              message = "observed user services must receive the user failure-notify drop-in";
            }
            {
              # A generated job reports its own failure even when nothing
              # observes it, which is the whole point of attaching at
              # registration rather than per module.
              assertion =
                config.systemd.services.sinnix-failure-attach-plain.onFailure
                == [ "sinnix-unit-failure-notify@%n.service" ];
              message = "generated jobs must attach the failure-notify template";
            }
            {
              # ...and exactly once: an observed job inherits it from its
              # surface instead of naming the same dependency a second time.
              assertion =
                config.systemd.services.sinnix-failure-attach-observed.onFailure == [ ]
                &&
                  config.systemd.services.sinnix-failure-attach-observed.unitConfig.OnFailure
                  == [ "sinnix-unit-failure-notify@%n.service" ];
              message = "an observed job must carry the failure-notify template once, via its surface";
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
            # The container backends pull in hardware.nvidia-container-toolkit,
            # whose upstream assertion demands a configured NVIDIA driver. This
            # spec evaluates unit wiring on a minimal test host with no GPU
            # stack, so suppress that one assertion rather than dragging the
            # whole driver closure into the check.
            hardware.nvidia-container-toolkit.suppressNvidiaDriverAssertion = true;
          })
        ];
        # Provably fails when: a backend declares `bindsTo` on its proxy; a
        # proxy socket's ListenStream drifts from its inventory
        # publicEndpoint; a proxy's socket-proxyd target drifts from its
        # backendEndpoint; a conflicts edge is added or removed on one side
        # of the gpu-inference mesh; llama-cpp or STT is admitted into it.
        assertions =
          config:
          let
            # Every socket-proxy front door, read from the inventory rather
            # than listed here, so a new backend is covered the day it is
            # declared.
            proxySurfaces = lib.filterAttrs (
              _: surface:
              (surface.activation.mode or "direct") == "socket-proxy" && (surface.kind or "service") == "socket"
            ) config.sinnix.runtime.inventory.surfaces;
            proxies = lib.mapAttrsToList (_: surface: {
              name = lib.removeSuffix ".socket" surface.unit;
              inherit (surface) activation;
            }) proxySurfaces;
            proxyNames = map (proxy: proxy.name) proxies;
            execStartOf = name: config.systemd.services.${name}.serviceConfig.ExecStart;
            backendUnitsOf =
              proxyName:
              lib.filter (unit: lib.elem "${proxyName}.service" (config.systemd.services.${unit}.partOf or [ ])) (
                lib.attrNames config.systemd.services
              );
            gpuInferenceUnits = lib.concatMap (backend: [
              backend.service
              backend.proxy
            ]) (lib.attrValues gpuInferenceBackends);
            gpuInferenceBackends = {
              ollama = {
                service = "ollama.service";
                proxy = "ollama-proxy.service";
              };
              koboldcpp = {
                service = "koboldcpp.service";
                proxy = "koboldcpp-proxy.service";
              };
              comfyui = {
                service = "podman-comfyui.service";
                proxy = "comfyui-proxy.service";
              };
              tts = {
                service = "podman-openedai-speech.service";
                proxy = "tts-proxy.service";
              };
              musicgen = {
                service = "podman-musicgen.service";
                proxy = "musicgen-proxy.service";
              };
              ocr = {
                service = "podman-ocr.service";
                proxy = "ocr-proxy.service";
              };
              muse-glimmer = {
                service = "muse-glimmer.service";
                proxy = "muse-glimmer-proxy.service";
              };
            };
            conflictsOf = unit: config.systemd.services.${lib.removeSuffix ".service" unit}.conflicts or [ ];
          in
          [
            {
              # Guards the PartOf-not-BindsTo invariant from ai-control's
              # mkProxy (see there for the mechanism): the edge must never
              # point back up, or a backend start pulls the proxy in outside
              # socket activation and both die.
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
              # The downward edge must exist, or an idle proxy exit leaves the
              # backend resident and the GPU held.
              assertion = builtins.all (proxyName: backendUnitsOf proxyName != [ ]) proxyNames;
              message = "Every socket-proxy front door must have at least one backend declaring PartOf= on it, or idling the proxy never releases the backend";
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
              # The inventory is what sinnix-observe and the hub read; the
              # units are what systemd runs. Checking them against
              # each other catches drift without pinning any port literal
              # here (which would only force a two-place edit).
              assertion = builtins.all (
                proxy: config.systemd.sockets.${proxy.name}.listenStreams == [ proxy.activation.publicEndpoint ]
              ) proxies;
              message = "Each socket-proxy front door must listen on exactly the public endpoint its runtime inventory advertises";
            }
            {
              assertion = builtins.all (
                proxy:
                lib.hasInfix "systemd-socket-proxyd" (execStartOf proxy.name)
                && lib.hasSuffix " ${proxy.activation.backendEndpoint}" (execStartOf proxy.name)
              ) proxies;
              message = "Each socket proxy must forward to exactly the backend endpoint its runtime inventory advertises";
            }
            {
              assertion = builtins.all (
                proxy:
                proxy.activation.idleTimeout != null
                && lib.hasInfix "--exit-idle-time=${proxy.activation.idleTimeout}" (execStartOf proxy.name)
              ) proxies;
              message = "Each socket proxy must carry the bounded idle timeout its runtime inventory advertises";
            }
            {
              # A proxy forwards the moment ExecStart runs; a backend binds
              # its port only after loading weights. Where the inventory
              # claims a readiness bound, a real gate must implement it.
              assertion = builtins.all (
                proxy:
                proxy.activation.readinessTimeout == null
                || lib.hasInfix "wait-backend" (
                  config.systemd.services.${proxy.name}.serviceConfig.ExecStartPre or ""
                )
              ) proxies;
              message = "A proxy advertising a readiness timeout must gate ExecStart on a real backend accept, or a cold request is refused instead of queued";
            }
            {
              # Full symmetry across the GPU-inference backends: every
              # (service, proxy) pair must conflict with every other
              # backend's pair in both directions. An asymmetric conflict set
              # is exactly the bug this check exists to catch.
              assertion = lib.all (
                backendA:
                lib.all (
                  backendB:
                  backendA == backendB
                  ||
                    lib.all
                      (
                        unitA:
                        lib.all (unitB: lib.elem unitB (conflictsOf unitA) && lib.elem unitA (conflictsOf unitB)) [
                          gpuInferenceBackends.${backendB}.service
                          gpuInferenceBackends.${backendB}.proxy
                        ]
                      )
                      [
                        gpuInferenceBackends.${backendA}.service
                        gpuInferenceBackends.${backendA}.proxy
                      ]
                ) (lib.attrNames gpuInferenceBackends)
              ) (lib.attrNames gpuInferenceBackends);
              message = "Every GPU-inference backend's service and proxy units must conflict symmetrically with every other backend's";
            }
            {
              # The two deliberate exemptions, checked directly rather than
              # trusted by omission. llama-cpp is the CPU-pinned reranker and
              # sinnix-stt is CPU-only Parakeet: both must stay available
              # while a GPU model is resident, in both directions.
              assertion =
                let
                  exempt = [
                    "llama-cpp.service"
                    "llama-cpp-proxy.service"
                    "sinnix-stt.service"
                    "stt-proxy.service"
                  ];
                in
                lib.all (
                  unit:
                  conflictsOf unit == [ ]
                  && lib.all (meshUnit: !(lib.elem unit (conflictsOf meshUnit))) gpuInferenceUnits
                ) exempt;
              message = "The CPU-only reranker and STT hub must stay outside the gpu-inference admission mesh, in both directions";
            }
            {
              # The AI factory generates units; it must not swallow the
              # command each service actually runs.
              assertion =
                lib.hasInfix "sinnix-stt" (execStartOf "sinnix-stt")
                && lib.hasInfix "podman" (execStartOf "podman-openedai-speech");
              message = "The AI factory must leave the native and containerized launch commands visible in their units";
            }
            {
              # LiteLLM routes to several independently activated backends.
              # Requiring Ollama here starts its GPU occupant for every
              # gateway request and evicts direct GPU backends such as Glimmer.
              assertion =
                !(lib.elem "ollama-proxy.service" (config.systemd.services.litellm.requires or [ ]))
                && !(lib.elem "ollama-proxy" (
                  config.sinnix.runtime.inventory.surfaces."litellm-proxy".activation.dependsOn or [ ]
                ));
              message = "LiteLLM must not unconditionally start the Ollama GPU backend; model backends activate independently";
            }
          ];
      };
      aiActivationEvaluated = evalTestSpec system aiActivationSpec;
      sinexCachePrebuildSpec = mkFeatureTest {
        name = "sinex-cache-prebuild-agentctl";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          ({ ... }: {
            sinnix.services.sinex-cache-prebuild.enable = true;
          })
        ];
        # The scheduled trigger must submit the declared operation, not start
        # a host-scoped build directly. The descriptor itself is checked in
        # agentctl-operation-contract; this check exercises its rendered
        # systemd submission route.
        assertions =
          config:
          let
            service = config.systemd.user.services.sinex-cache-prebuild.serviceConfig;
          in
          [
            {
              assertion =
                lib.hasInfix "/bin/agentctl job start sinnix sinex_cache_prebuild" service.ExecStart
                && service.TimeoutStartSec == "1min";
              message = "the Sinex cache-prebuild timer must submit the bounded named AgentCTL operation";
            }
          ];
      };
      sinexCachePrebuildEvaluated = evalTestSpec system sinexCachePrebuildSpec;
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
          # The Lua provider emits one semantic bind call per entry. Keep the
          # aggregate here so the collision check covers ordinary, locked, and
          # mouse binds together.
          hyprSettings.bind or [ ]
        );
      groupLuaConfig =
        groupEvaluated.config.home-manager.users.sinity.xdg.configFile."hypr/hyprland.lua".text;
      groupLuaStartup =
        groupEvaluated.config.home-manager.users.sinity.xdg.configFile."hypr/sinnix-startup.lua".text;
    in
    {
      # Provably fails when: a surface's `resources` override stops
      # reaching effectiveResources, a resource-class default stops merging
      # under an override, or an observed surface stops receiving the
      # failure-notify attachment. Those claims live in the spec's
      # assertions (forced by evalTestSpec); this derivation exists to force
      # the evaluation and to publish the rendered inventory.
      checks.runtime-surface-policy = pkgs.runCommand "runtime-surface-policy-check" { } ''
        cat > "$out" <<'EOF_INVENTORY'
        ${inventoryJson}
        EOF_INVENTORY
      '';
      # Provably fails when: any socket-proxy surface's unit wiring drifts
      # from the endpoints/timeouts its inventory entry advertises, or the
      # gpu-inference conflicts mesh loses symmetry. Claims live in the
      # spec's assertions; this derivation forces the evaluation.
      checks.ai-activation = pkgs.runCommand "ai-activation-check" { } ''
        cat > "$out" <<'EOF_INVENTORY'
        ${builtins.toJSON aiActivationEvaluated.config.sinnix.runtime.inventory}
        EOF_INVENTORY
      '';
      # Provably fails when the scheduled cache prebuild bypasses the named
      # AgentCTL project operation or keeps the old build-length timeout on
      # the short submission unit. The spec forces the rendered user service.
      checks.sinex-cache-prebuild-agentctl = pkgs.runCommand "sinex-cache-prebuild-agentctl-check" { } ''
        printf '%s\n' ${
          lib.escapeShellArg (
            builtins.toJSON {
              execStart =
                sinexCachePrebuildEvaluated.config.systemd.user.services.sinex-cache-prebuild.serviceConfig.ExecStart;
            }
          )
        } > "$out"
      '';
      # Provably fails when: Muse Glimmer is added to the Ollama load
      # roster (the packaged Ollama cannot load its architecture), or
      # LiteLLM's api_base for it drifts from the muse-glimmer-proxy
      # endpoint the runtime inventory advertises. Both are cross-file
      # agreements; the port literal is deliberately not restated here.
      checks.local-model-roster =
        let
          glimmerEntry = lib.findFirst (
            entry: entry.model_name == "local-glimmer"
          ) null localModels.litellmModelList;
          gemma26AbliteratedEntry = lib.findFirst (
            entry: entry.model_name == "local-gemma4-26b-abliterated"
          ) null localModels.litellmModelList;
          glimmerEndpoint =
            aiActivationEvaluated.config.sinnix.runtime.inventory.surfaces.muse-glimmer-proxy.activation.publicEndpoint;
        in
        assert lib.assertMsg (
          !lib.elem "muse-glimmer" localModels.ollamaLoadModels
        ) "Muse Glimmer is served by its own llama.cpp unit and must not be in the Ollama load roster";
        assert lib.assertMsg (
          glimmerEntry != null
        ) "The local model roster must expose Muse Glimmer to LiteLLM as local-glimmer";
        assert lib.assertMsg (glimmerEntry.litellm_params.api_base == "http://${glimmerEndpoint}/v1")
          "LiteLLM's local-glimmer api_base must be the muse-glimmer-proxy endpoint the runtime inventory advertises";
        assert lib.assertMsg (glimmerEntry.litellm_params.api_key == "sk-local")
          "LiteLLM's local-glimmer entry must carry the loopback backend credential required by the OpenAI provider";
        assert lib.assertMsg (
          gemma26AbliteratedEntry != null
          &&
            gemma26AbliteratedEntry.litellm_params.model
            == "ollama_chat/hf.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF:Q4_K_M"
          && lib.elem "hf.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF:Q4_K_M" localModels.ollamaLoadModels
        ) "The Gemma 4 26B abliterated model must be both pulled by Ollama and exposed through LiteLLM";
        pkgs.runCommand "local-model-roster-check" { } ''
          cat > "$out" <<'EOF_ROSTER'
          ${localModelRosterJson}
          EOF_ROSTER
        '';
      # Parse the actual Home Manager-rendered Lua through the compositor.
      # This exercises the API contract, including structured monitor rules.
      checks.hyprland-lua-generated = pkgs.runCommand "hyprland-lua-generated-check" { } ''
        cat > hyprland.lua <<'EOF_HYPRLAND_LUA'
        ${groupLuaConfig}
        EOF_HYPRLAND_LUA
        export HOME="$PWD/home"
        export XDG_CONFIG_HOME="$HOME/.config"
        install -d -m 0700 "$XDG_CONFIG_HOME/hypr"
        cat > "$HOME/.config/hypr/sinnix-startup.lua" <<'EOF_HYPRLAND_STARTUP'
        ${groupLuaStartup}
        EOF_HYPRLAND_STARTUP
        export XDG_RUNTIME_DIR="$PWD/runtime"
        install -d -m 0700 "$XDG_RUNTIME_DIR"
        ${pkgs.hyprland}/bin/Hyprland --config "$PWD/hyprland.lua" --verify-config
        touch "$out"
      '';
      # Provably fails when: a second bind claims a chord an existing bind
      # already uses (verified by duplicating "SUPER SHIFT, F").
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
              all(.[]; (._args | length) == 3 and (._args[0] | type) == "string" and (._args[2].description | type) == "string")
              and (map({chord: ._args[0]}) | group_by(.chord) | map(select(length > 1)) | length) == 0
            ' bindings.json >/dev/null
            touch "$out"
          '';
    };
}
