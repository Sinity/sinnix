# Local AI activation

The local AI backends use loopback socket activation. Clients retain the stable front doors `127.0.0.1:11434` for Ollama, `127.0.0.1:5001` for KoboldCpp, `127.0.0.1:8090` for the whisper.cpp STT hub, and `127.0.0.1:4000` for LiteLLM. The daemon ports are private loopback endpoints and are reachable only through their corresponding `systemd-socket-proxyd` unit.

The proxy starts the existing backend on demand and exits after 30 seconds without an open connection. The backend is bound to the proxy lifecycle, so the clean idle exit tears down the service and releases its CPU, RAM, and GPU allocation. Ollama, KoboldCpp, and the whisper STT hub share the `gpu-inference` admission key and have systemd conflicts in every direction, so a transcription request can never deadlock against a resident LLM.

The whisper hub answers the OpenAI-compatible `/v1/audio/transcriptions` route (whisper.cpp's native `/inference` endpoint, repointed via `--inference-path`) so any OpenAI Whisper API client — hermes, later the phone and capture-audio lanes, and future engine swaps (Parakeet, Voxtral) — can speak to it unmodified (see `sinnix-mke`).

Streaming responses and WebSocket-style sessions are deliberate long-lived protocol exceptions. Their connection keeps the proxy active. They are not forcibly terminated by the idle timer; teardown begins only after the connection closes and the proxy has been idle for the configured interval. The LiteLLM front door preserves the existing LiteLLM-to-Ollama request path through the Ollama proxy.

The canonical activation, endpoint, dependency, idle, and exclusivity metadata is serialized in `/etc/sinnix/runtime-inventory.json`. The service modules remain the owners of backend commands and model configuration.
