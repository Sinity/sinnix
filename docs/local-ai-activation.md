# Local AI activation

Most local AI backends use on-demand socket activation. Caddy checks Host and browser provenance on the public HTTP entrance, then connects to a private systemd socket. Accepted requests start the backend; an idle systemd proxy stops it after its declared window. A TCP connection or refused HTTP request does not activate a model. `sinnix ai list` distinguishes boot, on-demand and manual services from the runtime inventory and installed units.

## Service map

| Capability             | Front door        | Main command or model                                                                                                                     | Lifecycle                        | Resource notes                                       |
| ---------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ---------------------------------------------------- |
| Ollama text and vision | `127.0.0.1:11434` | `local-chat`, `local-vision`, `local-coder`, `local-coder-moe`, `local-reasoner`, `local-thinker`, `local-multimodal-moe`, `local-reader` | on demand                        | CUDA, one GPU inference occupant                     |
| LiteLLM gateway        | `127.0.0.1:4000`  | OpenAI `/v1/chat/completions` and Anthropic `/v1/messages`                                                                                | on demand                        | translates agent clients to local backends           |
| Muse Glimmer           | `127.0.0.1:8083`  | direct llama.cpp model `muse-glimmer` (abliterated Q4_K_M)                                                                                | on demand, 15 minute idle window | CUDA plus CPU/RAM hybrid, one GPU inference occupant |
| Qwen VRAM profile      | `127.0.0.1:8085`  | direct llama.cpp fully resident Qwen profile                                                                                              | on demand, 15 minute idle window | CUDA, one GPU inference occupant                     |
| Open WebUI             | `127.0.0.1:8080`  | browser chat over Ollama and LiteLLM                                                                                                       | on demand, 10 min idle           | an open tab keeps it running                         |
| llama.cpp reranker     | `127.0.0.1:8081`  | `/v1/rerank`                                                                                                                              | on demand                        | CPU resident by policy, outside GPU admission        |
| Speech to text         | `127.0.0.1:8090`  | `/v1/audio/transcriptions` or `sinnix stt`                                                                                                | on demand                        | Parakeet CPU service                                 |
| Kokoro TTS             | `127.0.0.1:8890`  | `/v1/audio/speech`                                                                                                                        | on demand                        | CPU service                                          |
| OpenedAI Speech        | `127.0.0.1:8000`  | `/v1/audio/speech`                                                                                                                        | on demand                        | container, GPU admission                             |
| ComfyUI                | `127.0.0.1:8188`  | browser and ComfyUI API                                                                                                                   | on demand                        | container, GPU admission                             |

OpenedAI Speech and ComfyUI are part of the optional
`sinnix.profiles.ai-media` aggregate and are absent by default. Model weights
and application state remain on `/realm` while the profile is disabled.

Open WebUI seeds its speech settings from an enabled provider: OpenedAI Speech
when enabled, otherwise Kokoro. With neither enabled it leaves the upstream
speech defaults alone. Existing persisted audio settings take precedence over
these defaults; switch those through Open WebUI's configuration API when changing
providers, preserving unrelated settings.

The llama.cpp profiles listen only on a Unix socket under `/run/<profile>/`, so
the Caddy front door is their only TCP entrance.

Kokoro's RAM and swap bounds apply directly to its Podman container. Its model
process is in a separate cgroup from the systemd client unit, whose memory
counter does not describe the model's working set. These limits do not govern
other AI containers.

The canonical model roster is `flake/data/local-models.nix`. The canonical port and front-door map is `flake/data/ports.nix`. Edit those sources when changing the platform. Do not add a model only to LiteLLM or only to an agent wrapper.

## The operator control plane

Use the `sinnix ai` front door for lifecycle operations:

```bash
sinnix ai list
sinnix ai status
sinnix ai status muse-glimmer
sinnix ai gpu
sinnix ai start muse-glimmer
sinnix ai stop muse-glimmer
sinnix ai logs muse-glimmer -n 100
sinnix ai pin muse-glimmer 2h
sinnix ai unpin muse-glimmer
```

`start` is useful when you want the cold load to happen before sending work. A first Glimmer load can take several minutes because the 17 GB GGUF is being mapped and the hybrid layer fit is computed. `pin` holds the private activation socket through a transient user unit. Its socket is accessible only to the operator and Caddy. It releases at the deadline, or earlier if the backend closes the connection. The pin is a transient user unit, releases automatically, and does not survive a reboot.

The GPU services share an exclusive `gpu-inference` resource. Ollama, the llama.cpp GPU profiles, ComfyUI, and the GPU TTS service cannot use the card concurrently. Starting one can stop a conflicting resident service. Check before and after a switch with `sinnix ai status` and `sinnix ai gpu`.

## Muse Glimmer

Glimmer is served directly by llama.cpp because the packaged Ollama build does not load its architecture. nixpkgs' llama.cpp supports it from v0.4.0. The service loads the abliterated 30B Q4_K_M GGUF from `/realm/library/model/gguf/Muse-Glimmer-30B-Abliterated-Q4_K_M.gguf` with these fixed runtime settings:

- `--n-gpu-layers auto` and `--fit on` place as many layers as fit in the RTX 3080 and keep the rest in system RAM.
- `--fit-target 1536` leaves approximately 1.5 GiB of VRAM for the desktop and transient buffers.
- `--ctx-size 32768` and `--parallel 1` give one caller a full 32K context.
- `--no-mmproj` keeps the optional vision projector out of the text-only service.
- Jinja templating and medium reasoning are enabled.

### Direct smoke test

The direct endpoint accepts the OpenAI chat-completions shape. The model field can be `muse-glimmer`:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8083/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "muse-glimmer",
    "messages": [{"role": "user", "content": "Reply with exactly GLIMMER_OK and nothing else."}],
    "max_tokens": 128,
    "temperature": 0
  }' | jq .
```

Reasoning tokens count against `max_tokens`. If a request ends with `finish_reason: "length"` and an empty visible answer, repeat it with `256` or `512` tokens. A successful smoke test has visible content `GLIMMER_OK`, `finish_reason: "stop"`, and a `system_fingerprint` naming the llama.cpp build.

To inspect the hybrid placement and throughput while it is loaded:

```bash
sinnix ai gpu
systemctl status muse-glimmer.service muse-glimmer-proxy.service --no-pager
sinnix ai logs muse-glimmer -n 100
```

The llama.cpp startup log prints the layer placement. On this machine, a normal loaded run uses roughly 7.2 GiB of VRAM and about 13.4 GiB of process RSS. The measured decode rate is approximately 4.8 tokens per second for this deployment. Prompt ingestion and long reasoning traces take longer than the visible answer suggests.

### Use Glimmer through LiteLLM

LiteLLM exposes the same backend as `local-glimmer` on port 4000. This is the preferred route for generic OpenAI clients and the local agent wrappers:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:4000/v1/chat/completions \
  -H 'Authorization: Bearer sk-local' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-glimmer",
    "messages": [{"role": "user", "content": "Give me a one-sentence summary of hybrid CPU/GPU inference."}],
    "max_tokens": 256,
    "temperature": 0.7
  }' | jq .
```

List the models currently advertised by the gateway:

```bash
curl --fail --silent http://127.0.0.1:4000/v1/models | jq '.data[].id'
```

The gateway path can start both LiteLLM and the selected backend. The first request can therefore be a cold request. Use `sinnix ai pin muse-glimmer 2h` before a longer session if you want to avoid an idle teardown.

## The other local language models

The model name is the stable LiteLLM name. The Ollama tag is the storage and pull name:

| LiteLLM name                   | Ollama tag                                                 | Intended use                                |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------- |
| `local-chat`                   | `huihui_ai/gemma-4-abliterated:12b`                        | daily text chat                             |
| `local-vision`                 | `gemma4:12b-it-qat`                                        | text plus image/audio input                 |
| `local-coder`                  | `qwen2.5-coder:7b`                                         | fast coding and triage                      |
| `local-coder-moe`              | `qwen3-coder:30b`                                          | slower, stronger coding stretch tier        |
| `local-reasoner`               | `gpt-oss:20b`                                              | general reasoning and agent jobs            |
| `local-thinker`                | `qwen3:30b`                                                | reasoning-heavy general work                |
| `local-multimodal-moe`         | `gemma4:26b`                                               | larger multimodal generalist                |
| `local-gemma4-26b-abliterated` | `hf.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF:Q4_K_M` | abliterated larger multimodal MoE           |
| `local-reader`                 | `hf.co/rbehzadan/ReaderLM-v2.gguf`                         | HTML to Markdown or JSON                    |
| `local-glimmer`                | direct llama.cpp                                           | dense reasoning with CPU/RAM hybrid offload |

Use the Ollama API when you need Ollama-specific options or model management:

```bash
ollama list
ollama pull qwen2.5-coder:7b
curl --fail --silent http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "Explain this function."}],
    "stream": false
  }' | jq .message
```

The RAG embedding model is `qwen3-embedding:0.6b`. It is used by Open WebUI and is not advertised as a chat model through LiteLLM. Experimental embedding and reader pulls are kept at the end of the roster so one unsupported model does not prevent the core pulls from completing.

## Driving local models from agents

The local agent profiles use LiteLLM and default to `local-chat`:

```bash
claude-local
codex-local
hermes-local
```

Select another advertised model with the client’s normal model option:

```bash
claude-local --model local-glimmer
codex-local --model local-glimmer
hermes-local --model local-coder
```

The same wrappers can select `local-coder`, `local-reasoner`, `local-thinker`, or the multimodal model. Glimmer is a useful choice for bounded batch work, extraction, judging, and autonomous jobs. `local-coder` is the better first choice for interactive coding because it stays GPU-resident and avoids the 30B hybrid cold path.

## Open WebUI

Open `http://127.0.0.1:8080` or its hub frontend on port 8881; the first request starts it, which takes a while on a cold start. It stops after 10 minutes without connections; an open tab's websocket counts as a connection. `sinnix ai start|stop open-webui` controls it explicitly.

The hub frontend applies the hub's own request checks and then forwards as a native client. There is no login (`WEBUI_AUTH=False`, single operator).

The configuration provides Ollama models and LiteLLM model routes, including the direct llama.cpp profiles, through `OPENAI_API_BASE_URLS`. Document embeddings use the roster's Ollama embedding model. The actual model list still depends on those owners being reachable.

## Speech, reranking, and media generation

Speech to text is the CPU-only Parakeet hub. It can be driven through the purpose-built CLI or the OpenAI-compatible API:

```bash
sinnix stt lanes
sinnix stt transcribe recording.wav
sinnix stt diarize recording.wav
sinnix stt models
curl -F file=@recording.wav -F model=parakeet-tdt-0.6b-v3 \
  http://127.0.0.1:8090/v1/audio/transcriptions
```

The reranker is the llama.cpp endpoint at `127.0.0.1:8081` and answers `/v1/rerank`. It runs with zero model layers on the GPU by policy, so it can coexist with a resident language model. Kokoro at `127.0.0.1:8890` and OpenedAI Speech at `127.0.0.1:8000` answer `/v1/audio/speech`. ComfyUI is at `http://127.0.0.1:8188`. Start enabled services with `sinnix ai start <name>` and stop them when the generation is complete.

## Troubleshooting

- A first Glimmer request can wait during model load. Check `sinnix ai logs muse-glimmer`; a 503 during the initial load is different from a persistent load failure.
- `unknown model architecture: muse-glimmer` means an old llama.cpp package is running. The installed llama.cpp must be v0.4.0 or newer.
- Do not run `ollama pull muse-glimmer`. This deployment is intentionally not in the Ollama pull roster.
- If a request returns `finish_reason: "length"` with no visible content, raise `max_tokens`; the reasoning trace consumed the budget.
- If VRAM is tight, inspect `sinnix ai status` and stop the current GPU occupant before starting another. The services are designed to be mutually exclusive.
- After configuration changes, run `nix develop --command switch` from the intended Sinnix checkout, then verify `nixos-version --configuration-revision`. The wrapper builds the devshell's evaluated source and checks that source's revision against a fresh `origin/master` before activation. It refuses a dirty or stale source. `SINNIX_ALLOW_DIRTY=1` explicitly permits uncommitted files; it does not permit a stale revision. A successful switch is confirmed when the live revision matches the repository commit.

Container-backed AI services enable the shared Podman runtime through the AI service factory. NVIDIA CDI is enabled only when an enabled container backend declares `requiresCuda`; CPU-only Kokoro does not require an NVIDIA driver. OCI layers stay under the managed service-state root.

The runtime inventory at `/etc/sinnix/runtime-inventory.json` records the declared endpoints, activation modes, resource class, idle windows, and GPU admission relationships for these services.

### Browser protection

Browser pages are kept away from these services in two places. Caddy checks Host, Origin and Fetch Metadata on every public front door before a request can activate a backend. Chrome's Local Network Access gate (Chrome 142 and later) makes a public website ask for permission before it can reach `localhost` or `127.0.0.1` at all, including through DNS rebinding. Backends get no source patches: the llama.cpp profiles are reachable only through Caddy, and Ollama, LiteLLM and Open WebUI keep their upstream Host and CORS handling on their private loopback ports.

### HTTP activation boundary

The system Caddy service fronts the registry-declared loopback ports independently of the tailnet hub. Each private activation socket is owned by the operator, with group access for Caddy and mode `0660`. Its unit name carries a hash of its definition (`<name>-proxy-<hash>.socket`, named by the proxy service's `Sockets=`), because NixOS activation does not restart a changed socket unit; a changed definition becomes a new unit that activation starts. STT declares a native-only entrance matching its receiver, so even same-origin browser metadata is refused before it loads. The backend and proxy retain the readiness wait, idle timeout, native manual-start route and GPU conflict mesh. Their systemd lifetimes are bound so a natural proxy idle exit releases the backend. Manual prewarming acquires the listening socket before starting its proxy; idle timing starts after the first proxy connection. Declared public-API consumers (such as the Ollama model loader) require the HTTP gate before they start. Caddy does not pool upstream connections, so it cannot extend a backend's idle window after a request ends. Streaming and WebSocket connections remain active work until they close.

Caddy's administration entrance is an owner-only Unix socket under `/run/caddy`; it does not expose an additional TCP control API. `ai-http-boundary` checks the generated request gate with no models. `ai-http-activation-vm` checks the actual systemd/Caddy lifecycle using lightweight fake backends, including zero starts for refused requests, idle release and exclusive-resource transitions.
