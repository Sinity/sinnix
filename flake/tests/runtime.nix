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
            assertion =
              config.home-manager.users.sinity.systemd.user.services.runtime-policy-user.Unit.OnFailure
              == [ "sinnix-health-transition@%n" ];
            message = "observed user services must receive the user health transition template";
          }
        ];
      };
      evaluated = evalTestSpec system spec;
      inventoryJson = builtins.toJSON evaluated.config.sinnix.runtime.inventory;
      aiActivationSpec = mkFeatureTest {
        name = "ai-activation";
        feature = "sinnix.features.cli.polylogue.enable";
        extraModules = [
          ({ ... }: {
            sinnix.services.ollama.enable = true;
            sinnix.services.koboldcpp.enable = true;
            sinnix.services.litellm.enable = true;
            sinnix.services.open-webui.enable = true;
            sinnix.services.whisper.enable = true;
            sinnix.services.tts.enable = true;
          })
        ];
        assertions = config: [
          {
            assertion = config.systemd.sockets.ollama-proxy.listenStreams == [ "127.0.0.1:11434" ];
            message = "Ollama must expose only its socket-activated loopback front door";
          }
          {
            assertion = config.systemd.services.ollama.unitConfig.PartOf == [ "ollama-proxy.service" ];
            message = "Stopping an idle Ollama proxy must stop its backend";
          }
          {
            assertion = config.systemd.services.ollama.unitConfig.BindsTo == [ "ollama-proxy.service" ];
            message = "An idle proxy exit must tear down the Ollama backend cgroup";
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
              config.systemd.services.whisper-server.serviceConfig.ExecStart != null
              && lib.hasInfix "whisper-server" config.systemd.services.whisper-server.serviceConfig.ExecStart;
            message = "The AI factory must leave the native whisper command visible";
          }
          {
            assertion = config.systemd.sockets.whisper-proxy.listenStreams == [ "127.0.0.1:8090" ];
            message = "Whisper must expose only its socket-activated loopback front door (the shared STT hub)";
          }
          {
            assertion =
              config.systemd.services.whisper-server.unitConfig.PartOf == [ "whisper-proxy.service" ]
              && config.systemd.services.whisper-server.unitConfig.BindsTo == [ "whisper-proxy.service" ];
            message = "An idle whisper-proxy exit must tear down the whisper backend cgroup";
          }
          {
            assertion =
              lib.hasInfix "systemd-socket-proxyd" config.systemd.services.whisper-proxy.serviceConfig.ExecStart
              && lib.hasInfix "--exit-idle-time=30s" config.systemd.services.whisper-proxy.serviceConfig.ExecStart;
            message = "Whisper activation must use the idle-aware systemd socket proxy";
          }
          {
            assertion = lib.hasInfix "--inference-path /v1/audio/transcriptions" config.systemd.services.whisper-server.serviceConfig.ExecStart;
            message = "The whisper hub must answer the OpenAI-compatible transcriptions route";
          }
          {
            assertion =
              config.sinnix.runtime.inventory.surfaces.whisper.activation.backendEndpoint == "127.0.0.1:8091"
              &&
                config.sinnix.runtime.inventory.surfaces.whisper-proxy.activation.publicEndpoint
                == "127.0.0.1:8090";
            message = "Runtime inventory must describe the public and private whisper activation endpoints";
          }
          {
            assertion =
              lib.elem "whisper-server.service" config.systemd.services.ollama.unitConfig.Conflicts
              && lib.elem "whisper-server.service" config.systemd.services.koboldcpp.unitConfig.Conflicts
              && lib.elem "ollama.service" config.systemd.services.whisper-server.unitConfig.Conflicts
              && lib.elem "koboldcpp.service" config.systemd.services.whisper-server.unitConfig.Conflicts;
            message = "The STT hub and GPU inference backends must be mutually exclusive (shared gpu-inference admission key)";
          }
          {
            assertion =
              config.systemd.services.podman-openedai-speech.serviceConfig.ExecStart != null
              && lib.hasInfix "podman" config.systemd.services.podman-openedai-speech.serviceConfig.ExecStart;
            message = "The AI factory must leave the container launch visible";
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
      groupBindingsJson = builtins.toJSON (
        groupEvaluated.config.home-manager.users.sinity.wayland.windowManager.hyprland.settings.bind or [ ]
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
              .surfaces.litellm.activation.dependsOn == ["ollama-proxy"]
            ' inventory.json >/dev/null
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
