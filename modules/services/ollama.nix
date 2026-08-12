# Ollama — local LLM/VLM inference hub (OpenAI-compatible API on 127.0.0.1:11434).
#
# This is the Tier-1 daily driver: Open WebUI and aichat both target it. Weights
# live on durable /realm (NOT the wear-limited root SSD); CUDA via the prebuilt
# `ollama-cuda`. Automatic VRAM<->RAM offload handles models that don't fully fit
# the 3080's 10 GB.
#
# DynamicUser note: the upstream unit sets DynamicUser=true *and* User=. When
# User= names an existing static account, systemd uses that account, which is
# what lets the daemon write the /realm models dir. We point it at the human
# user so the dir it owns (created via tmpfiles below) is writable.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
mkServiceModule {
  name = "ollama";
  description = "Ollama local LLM/VLM inference hub (CUDA)";
  surface = {
    unit = "ollama.service";
    resourceClass = "interactive-agent"; # uncapped memory — required for RAM offload
    activation = {
      mode = "socket-proxy";
      publicEndpoint = "127.0.0.1:11434";
      backendEndpoint = "127.0.0.1:11435";
      idleTimeout = "30s";
      exclusiveResource = "gpu-inference";
      dependsOn = [ "ollama-proxy" ];
      # Model pulls are exactly the long-running-consumer case the
      # activation contract exists for.
      consumers = [
        {
          unit = "ollama-model-loader";
          environment.OLLAMA_HOST = "127.0.0.1:11434";
        }
      ];
    };
    observe = {
      enable = true;
      restartable = true;
    };
  };
  extraOptions = {
    autoStart = args.lib.mkOption {
      type = args.lib.types.bool;
      default = true;
      description = "Start Ollama automatically at boot.";
    };
    loadModels = args.lib.mkOption {
      type = args.lib.types.listOf args.lib.types.str;
      # Sourced from flake/data/local-models.nix (the roster shared with
      # litellm.nix's model_list and open-webui.nix's RAG_EMBEDDING_MODEL,
      # with per-model rationale) — edit the roster there, not here. A
      # failed pull only fails the loader oneshot, not the system.
      default = helpers.data.localModels.ollamaLoadModels;
      description = "Models pre-pulled by the ollama-model-loader oneshot.";
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
      modelsDir = "${config.sinnix.paths.mediaRoot}/model/ollama";
      ollamaBin = lib.getExe pkgs.ollama-cuda;
      awkBin = lib.getExe pkgs.gawk;
      # Upstream's ollama-model-loader (nixpkgs services.ollama.loadModels)
      # pulls every tag in one `parallel` invocation with no per-model retry:
      # one transient transfer flake aborts the whole oneshot mid-list,
      # silently leaving the roster incomplete while
      # LiteLLM keeps advertising the missing model. Replace the generated
      # script with one that retries each tag independently (bounded
      # backoff), keeps going on exhaustion instead of aborting, then
      # verifies the full roster against `ollama list` and names exactly
      # which tags are still missing before failing the unit.
      modelLoaderScript = ''
        declare -a models=( ${lib.escapeShellArgs cfg.loadModels} )
        declare -a delays=(10 30 60 120)
        max_attempts=5
        declare -a failed_pulls=()

        for model in "''${models[@]}"; do
          attempt=1
          pulled=0
          while (( attempt <= max_attempts )); do
            echo "ollama-model-loader: pulling ''${model} (attempt ''${attempt}/''${max_attempts})"
            if ${ollamaBin} pull "''${model}"; then
              pulled=1
              break
            fi
            if (( attempt < max_attempts )); then
              delay="''${delays[attempt - 1]}"
              echo "ollama-model-loader: pull of ''${model} failed (attempt ''${attempt}/''${max_attempts}); retrying in ''${delay}s" >&2
              sleep "''${delay}"
            fi
            attempt=$(( attempt + 1 ))
          done
          if (( pulled == 0 )); then
            echo "ollama-model-loader: giving up on ''${model} after ''${max_attempts} attempts; continuing with remaining models" >&2
            failed_pulls+=("''${model}")
          fi
        done

        if (( ''${#failed_pulls[@]} > 0 )); then
          echo "ollama-model-loader: exhausted retries for: ''${failed_pulls[*]}" >&2
        fi

        # Roster verification. `ollama list` prints tags pulled without an
        # explicit tag with an added ":latest" suffix (e.g. hf.co/foo/bar.gguf
        # lists as hf.co/foo/bar.gguf:latest) -- treat `tag` and `tag:latest`
        # as the same model when comparing against the declared roster.
        installed="$(${ollamaBin} list | ${awkBin} 'NR > 1 {print $1}')"

        declare -a still_missing=()
        for model in "''${models[@]}"; do
          found=0
          while IFS= read -r have; do
            [ -z "''${have}" ] && continue
            if [ "''${have}" = "''${model}" ] || [ "''${have}" = "''${model}:latest" ]; then
              found=1
              break
            fi
          done <<< "''${installed}"
          if (( found == 0 )); then
            still_missing+=("''${model}")
          fi
        done

        if (( ''${#still_missing[@]} > 0 )); then
          echo "ollama-model-loader: roster verification failed, missing tags: ''${still_missing[*]}" >&2
          exit 1
        fi

        echo "ollama-model-loader: roster verified, all ''${#models[@]} declared models present"
      '';
    in
    {
      services.ollama = {
        enable = true;
        package = pkgs.ollama-cuda;
        # Dedicated static system user (created by the module). systemd uses the
        # static account over DynamicUser, so it can own/write the /realm models
        # dir. Reusing the human user would rewrite their home dir → HM conflict.
        user = "ollama";
        group = "ollama";
        host = "127.0.0.1";
        # 11434 is reserved for the socket-activated front door. Keep the
        # daemon on a private loopback port so clients cannot bypass lifecycle
        # admission and idle teardown.
        port = 11435;
        openFirewall = false;
        inherit modelsDir;
        inherit (cfg) loadModels;
        environmentVariables = {
          OLLAMA_FLASH_ATTENTION = "1";
          OLLAMA_KEEP_ALIVE = "30m";
          # 10 GB VRAM: keep one model resident at a time to avoid thrashing.
          OLLAMA_MAX_LOADED_MODELS = "1";
        };
      };

      # /realm is durable (separate fs, outside impermanence) — only create+own
      # the tree; no sinnix.persistence declaration needed.
      systemd.tmpfiles.rules = [
        # Shared parent owned by the human user; ollama subdir owned by the
        # ollama service account (0755 keeps the parent traversable).
        "d ${config.sinnix.paths.mediaRoot}/model 0755 ${user} users -"
        "d ${modelsDir} 0755 ollama ollama -"
      ];

      environment.systemPackages = [ pkgs.ollama-cuda ]; # `ollama` CLI on PATH

      systemd.services = lib.mkMerge [
        (lib.mkIf (!cfg.autoStart) {
          ollama.wantedBy = lib.mkForce [ ];
          ollama-model-loader.wantedBy = lib.mkForce [ ];
        })
        {
          ollama.partOf = [ "ollama-proxy.service" ];
          ollama.bindsTo = [ "ollama-proxy.service" ];
          ollama.conflicts = [
            "koboldcpp.service"
            "koboldcpp-proxy.service"
          ];
          # Full override (mkForce): the upstream `script` is a plain
          # (non-mkForce) definition, so an un-forced override here would
          # concatenate rather than replace it.
          ollama-model-loader.script = lib.mkForce modelLoaderScript;
        }
      ];
    };
} args
