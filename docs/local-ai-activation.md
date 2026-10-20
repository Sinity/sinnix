# Local AI activation

Most local AI backends use on-demand socket activation. Caddy checks Host and browser provenance on the public HTTP port, then connects to a private systemd socket. Accepted requests start the backend; an idle systemd proxy stops it after its declared window. A TCP connection or refused HTTP request does not activate a model. `sinnix ai list` distinguishes boot, on-demand and manual services from the runtime inventory and installed units.

## Service map

| Capability             | Proxy             | Main command or model                                                                                                                     | Lifecycle                        | Resource notes                                       |
| ---------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ---------------------------------------------------- |
| Ollama text and vision | `127.0.0.1:11434` | `local-chat`, `local-vision`, `local-coder`, `local-coder-moe`, `local-reasoner`, `local-thinker`, `local-multimodal-moe`, `local-reader` | on demand                        | CUDA, one GPU inference occupant                     |
| LiteLLM gateway        | `127.0.0.1:4000`  | OpenAI `/v1/chat/completions` and Anthropic `/v1/messages`                                                                                | on demand                        | translates agent clients to local backends           |
| Muse Glimmer           | `127.0.0.1:8083`  | direct llama.cpp model `muse-glimmer` (abliterated Q4_K_M)                                                                                | on demand, 15 minute idle window | CUDA plus CPU/RAM hybrid, one GPU inference occupant |
| Qwen VRAM profile      | `127.0.0.1:8085`  | direct llama.cpp fully resident Qwen profile                                                                                              | on demand, 15 minute idle window | CUDA, one GPU inference occupant                     |
| Open WebUI             | `127.0.0.1:8080`  | browser chat over Ollama and LiteLLM                                                                                                      | on demand, 10 min idle           | an open tab keeps it running                         |
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
the Caddy proxy is their only TCP entry point.

Kokoro's RAM and swap bounds apply directly to its Podman container. Its model
process is in a separate cgroup from the systemd client unit, whose memory
counter does not describe the model's working set. These limits do not govern
other AI containers.

The canonical model roster is `flake/data/local-models.nix`. The canonical port and proxy map is `flake/data/ports.nix`. Edit those sources when changing the platform. Do not add a model only to LiteLLM or only to an agent wrapper.

## Start, stop, and pin services

Use the `sinnix ai` command for lifecycle operations:

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

`start` prewarms a backend before work arrives. Glimmer can take several minutes to map its 17 GB GGUF and fit layers across GPU and RAM. `pin` keeps the private activation socket open through a transient user unit until its deadline, the backend closes the connection, or reboot. Only the operator and Caddy can access that socket.

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
set -o pipefail
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

The startup log records actual layer placement. Inspect current GPU usage and process memory rather than assuming an earlier measurement still applies. Prompt ingestion and reasoning add latency before visible output.

### Use Glimmer through LiteLLM

LiteLLM exposes the same backend as `local-glimmer` on port 4000. This is the preferred route for generic OpenAI clients and the local agent wrappers:

```bash
set -o pipefail
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
set -o pipefail
curl --fail --silent http://127.0.0.1:4000/v1/models | jq '.data[].id'
```

The gateway path can start both LiteLLM and the selected backend. The first request can therefore be a cold request. Use `sinnix ai pin muse-glimmer 2h` before a longer session if you want to avoid an idle teardown.

## Choose a model

[The model roster](../flake/data/local-models.nix) owns LiteLLM names, Ollama
pull tags, embedding models, and llama.cpp profiles. The advertised-model query
above shows the running gateway's names; `ollama list` shows installed Ollama
weights. These lists answer different questions: a gateway route does not prove
that its weights are present or its backend is ready.

Use `local-chat` for the wrappers' default chat route, `local-coder` for small
GPU-resident coding work, and `local-glimmer` for the hybrid Glimmer service.
Other reasoning and multimodal routes are defined in the roster. Change the
roster rather than maintaining a second model list here.

Use the Ollama API when you need Ollama-specific options or model management:

```bash
set -o pipefail
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

Open WebUI uses the roster's RAG embedding model directly through Ollama; it is not a LiteLLM chat route. Experimental embedding and reader pulls follow the core models so one unsupported pull cannot prevent the core pulls from completing.

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

Choose any advertised model with the client's model option. Glimmer suits bounded batch work, extraction, and judging; its hybrid load and decode cost make `local-coder` a better starting point for interactive coding.

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
- Activate configuration changes through [the repository activation procedure](../AGENTS.md#activation). Check both the installed revision and the affected endpoint or unit; a matching revision alone does not prove model readiness.

Container-backed AI services enable the shared Podman runtime through the AI service factory. NVIDIA CDI is enabled only when an enabled container backend declares `requiresCuda`; CPU-only Kokoro does not require an NVIDIA driver. OCI layers stay under the managed service-state root.

The runtime inventory at `/etc/sinnix/runtime-inventory.json` records the declared endpoints, activation modes, resource class, idle windows, and GPU admission relationships for these services.

### Browser protection

Browser pages are kept away from these services in two places. Caddy checks Host, Origin and Fetch Metadata on every public proxy before a request can activate a backend. Chrome's Local Network Access gate (Chrome 142 and later) makes a public website ask for permission before it can reach `localhost` or `127.0.0.1` at all, including through DNS rebinding. Backends get no source patches: the llama.cpp profiles are reachable only through Caddy, and Ollama, LiteLLM and Open WebUI keep their upstream Host and CORS handling on their private loopback ports.

### HTTP activation boundary

System Caddy fronts the registry's loopback ports independently of the tailnet
hub. The activation factory preserves these lifecycle rules:

- Private activation sockets have operator ownership, Caddy group access, and
  mode `0660`. Their names include a definition hash
  (`<name>-proxy-<hash>.socket`, listed in the proxy's `Sockets=`), so activation
  starts a new unit when a socket definition changes.
- STT accepts native clients only; even same-origin browser metadata is refused
  before model load. Public-API consumers such as the Ollama model loader wait
  for the HTTP gate before starting.
- Proxies wait for backend readiness and stop idle backends. Prewarming acquires
  the socket before starting the proxy; idle timing starts after its first
  connection. GPU services retain exclusive admission during this lifecycle.
- Caddy does not pool upstream connections. Streaming and WebSocket connections
  count as active work until they close; completed requests cannot keep a
  backend resident through a pooled connection.

Caddy's administration endpoint is an owner-only Unix socket under `/run/caddy`; it does not expose an additional TCP control API. `ai-http-boundary` checks the generated request gate with no models. `ai-http-activation-vm` checks the actual systemd/Caddy lifecycle using lightweight fake backends, including zero starts for refused requests, idle release and exclusive-resource transitions.
