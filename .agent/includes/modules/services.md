## Services (Daemons)

Long-running systemd services in `modules/services/`:

| Service                | Purpose                                         | Has UI?          |
| ---------------------- | ----------------------------------------------- | ---------------- |
| agent-gateway.nix      | Trusted local MCP gateway for coding agents     | No (MCP/HTTP)    |
| airvpn-seed.nix        | WireGuard tunnel namespace for Transmission     | No               |
| below.nix              | Facebook's cgroup resource monitoring           | Yes (TUI)        |
| borg-target.nix        | Remote Borg target metadata/options             | No               |
| comfyui.nix            | On-demand ComfyUI image/video workflow server   | Yes (web UI)     |
| koboldcpp.nix          | On-demand local LLM/image inference server      | Yes (web UI/API) |
| litellm.nix            | Local Anthropic/OpenAI-compatible model gateway | No (API)         |
| llama-cpp.nix          | Optional raw llama.cpp server                   | No (API)         |
| lynchpin.nix           | Data analysis hub (Python/DuckDB)               | No (background)  |
| machine-telemetry.nix  | Canonical host telemetry for Lynchpin analysis  | No (background)  |
| ml-containers.nix      | Shared Podman/NVIDIA CDI runtime for ML tools   | No               |
| musicgen.nix           | Optional containerized music/audio generation   | Yes (web UI/API) |
| ocr.nix                | Optional containerized OCR/document API         | No (API)         |
| ollama.nix             | Local LLM/VLM model hub                         | No (API)         |
| open-webui.nix         | Local LLM chat/RAG frontend                     | Yes (web UI)     |
| oracle.nix             | Daily reverse-prompting digest (timer+oneshot)  | No (background)  |
| polylogue.nix          | AI chat archive ingestion (via HM module)       | No (background)  |
| sinex.nix              | Sinnix-facing Sinex option declarations         | No               |
| sinex/bridge.nix       | Host bridge into upstream Sinex NixOS module    | No               |
| tailscale.nix          | Tailscale client/server policy                  | No               |
| terminal-capture.nix   | Shell session recording (transparent capture)   | No (background)  |
| transmission.nix       | BitTorrent daemon                               | Yes (web UI)     |
| tts.nix                | OpenAI-compatible local TTS container           | No (API)         |
| weechat-log-sealer.nix | Weechat capture log sealing                     | No               |
| whisper.nix            | Local whisper.cpp speech-to-text server         | No (API)         |

**Rule**: Primary purpose is **daemon**, UI is secondary/optional. Compare with `features/desktop/activitywatch.nix` where user wants **tracking**, daemon is implementation detail.
