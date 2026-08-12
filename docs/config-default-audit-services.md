# Service default audit

Audit date: 2026-08-07. Scope: `modules/services/`, `mkServiceModule`, runtime inventory surfaces, persistence declarations, activation policy, loopback endpoints, and incident-derived unit limits.

## Matrix

| Service family             | Files reviewed                                                                                                                                                                             | Classification                                   | Result                                                                                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime and capture        | `machine-telemetry.nix`, `below.nix`, `terminal-capture.nix`, `ops-reducer.nix`, `polylogue.nix`, `sinex-dev-db-reaper.nix`                                                                | substrate or capture policy                      | Retain explicit cadence, persistence, surface identity, resource overrides, and failure routing. These are not upstream-default noise.                                                                         |
| Local AI                   | `ollama.nix`, `litellm.nix`, `open-webui.nix`, `koboldcpp.nix`, `llama-cpp.nix`, `whisper.nix`, `comfyui.nix`, `tts.nix`, `musicgen.nix`, `ocr.nix`, `ml-containers.nix`, `ai-control.nix` | broad capability with quiescent/on-demand policy | Retain loopback binds, model/state paths, CUDA selection, auto-start choices, and service-specific commands. The corrected handoff keeps this breadth and delegates lifecycle consolidation to `sinnix-c32`.   |
| Agent and operator control | `agent-gateway.nix`, `oracle.nix`, `lynchpin.nix`                                                                                                                                          | user-facing control and scheduled maintenance    | Retain profile, tunnel, persistence, timer, and timeout settings. They are authority and evidence contracts, not generic service defaults.                                                                     |
| Network and storage        | `airvpn-seed.nix`, `tailscale.nix`, `transmission.nix`, `borg-target.nix`                                                                                                                  | operator and storage policy                      | Retain loopback, firewall, auto-start, target, and backup settings. `borg-target.nix` is a target declaration without a service enable option and remains a documented factory exception.                      |
| Messaging and maintenance  | `weechat-log-sealer.nix`, `sinex.nix`, `sinex/bridge.nix`, `oracle.nix`, `borg-target.nix`                                                                                                 | composite or scheduled policy                    | Retain explicit ordering, timer persistence, auxiliary-unit gating, and migration boundaries. `sinex/bridge.nix` is intentionally hand-rolled because its options/configuration span the upstream Sinex graph. |

## Factory and exception matrix

`mkServiceModule` remains the shared option and runtime-surface factory for ordinary services. The following exceptions are deliberate:

| File                               | Exception                                             | Evidence                                                                                                                                          |
| ---------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sinex.nix` and `sinex/bridge.nix` | Multi-file upstream graph and host-specific gating    | The bridge owns auxiliary database, NATS, runtime, persistence, and target relationships. Flattening it would hide service-specific dependencies. |
| `borg-target.nix`                  | Target/data declaration, not an enabled daemon module | It has no ordinary service enable contract and is consumed by backup configuration.                                                               |
| `hyprland`-adjacent user services  | Not in this directory                                 | Desktop user services remain feature-owned and are covered by the feature audit.                                                                  |

All ordinary service modules and the helper files were read. Explicit values fall into one of these retained policy classes: runtime identity, resource containment, persistence, loopback exposure, on-demand activation, hardening, dependency ordering, timeout, or incident recovery. No value was removed because no candidate had pinned upstream-default evidence while lacking local policy meaning.

## Verification

- The existing `runtime-surface-policy` fixture is the behavior gate for generated resource policy, surface registration, and effective inventory serialization.
- The live manifest after the latest switch reports 47 runtime surfaces and separate live systemd state. This audit found no service declaration that should be silently dropped from that inventory.
- The final switch for the adjacent runtime change succeeded. This documentation-only audit introduces no activation change.

No source service file, unit, persistence declaration, endpoint, or activation policy was changed. The parent `sinnix-ow0` retains the final whole-tree check and switch gate.
