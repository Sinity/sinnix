# Agent gateway

The Sinnix agent gateway is one official-SDK MCP implementation with three capability profiles. It exposes canonical project and runtime evidence, reuses the attested transient-systemd agent substrate, and keeps remote transport outside the MCP process.

## Architecture

```text
ChatGPT remote-readonly connector
    -> OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-mcp --profile remote-readonly
    -> shared project, job, artifact, audit, and observe services

Local coordinators
    -> sinnix-agent-control-mcp
    -> stdio: sinnix-agent-gateway --profile local-agent-control
    -> run_agent_prompt.sh and agent_job_control.sh
    -> transient systemd scope, manifest, cgroup, and bounded artifacts
```

There is no gateway-owned HTTP server, SSE parser, listening port, PID-only job authority, repository registry, or command registry. The official OpenAI tunnel owns the remote connection and launches the MCP server over stdio. The gateway uses the official MCP Python SDK v2 for protocol parsing and typed tool schemas.

## Capability profiles

| Profile               | Intended caller                                           | Read projects, jobs, artifacts, audit, machine | Launch and cancel jobs | Write projects                                   |
| --------------------- | --------------------------------------------------------- | ---------------------------------------------- | ---------------------- | ------------------------------------------------ |
| `remote-readonly`     | Current ChatGPT connector                                 | Yes                                            | No                     | No                                               |
| `local-agent-control` | Trusted local coordinators                                | Yes                                            | Yes                    | No                                               |
| `remote-operator`     | Local testing and a future write-capable remote workspace | Yes                                            | Yes                    | Yes, only for projects with `remoteWrite = true` |

Tool registration follows the profile. A denied capability is absent from `tools/list`, and the underlying service enforces the same capability again. `remote-readonly` therefore cannot obtain a write path by calling an unlisted function directly.

Ordinary full and browser agent profiles do not receive `agent-control`. Explicit orchestration profiles do. This keeps process mutation out of broad always-on tool surfaces.

## Interfaces

The configured commands are:

```bash
sinnix-agent-gateway-mcp --profile remote-readonly
sinnix-agent-control-mcp
sinnix-agent-gateway-schema remote-readonly
sinnix-agent-gateway --config /etc/sinnix/agent-gateway.json --profile remote-readonly info
```

`sinnix-agent-gateway-schema` emits a canonical, sorted tool manifest and SHA-256. Compare this hash with both the live tunnel `tools/list` response and the frozen ChatGPT connector snapshot whenever tools change. Updating the local server does not update an already approved connector schema.

The common read surface includes:

- `gateway_status` and `machine_report`
- `project_list`, `project_tree`, `project_read`, `project_search`, and `project_diff`
- `job_list`, `job_status`, and `job_read_output`
- `artifact_list` and `artifact_read`
- `audit_tail` and `audit_verify`

`local-agent-control` adds `agent_launch` and `job_cancel`. `remote-operator` also adds `project_write` and `project_apply_patch`.

## Project and path authority

`sinnix.projects.entries` is the only project registry. It is derived from the existing project paths in `modules/foundation.nix` and rendered into `/etc/sinnix/agent-gateway.json`. Remote visibility and writes are explicit per project.

Project paths are always relative. Reads and writes reject absolute paths, parent traversal, sensitive path components, and symlink escapes. Tree traversal does not follow symlinks. File reads apply the requested line range before the byte bound, so late ranges do not silently return the beginning of a large file. Git and ripgrep output is written to a temporary file and read back through a fixed response bound instead of being fully buffered in memory.

## Jobs and artifacts

The gateway does not implement another job runner. `agent_launch` calls the shared `run_agent_prompt.sh`, which creates a transient systemd scope and a versioned manifest containing the stable job ID, cgroup, unit, worktree, prompt digest, resource overrides, timeout, lifecycle, and artifact locations. `RuntimeMaxSec` enforces the declared timeout. Cancellation accepts only an attested job ID and verifies the unit, PID, cgroup, and working directory before stopping the scope.

Only an explicit environment allowlist reaches launched agents. Unrelated exported secrets are not inherited. Job state and generated prompt, manifest, log, and artifact metadata are private to the user.

Artifacts use random opaque UUIDs. The public metadata omits host paths, and reads use offset plus a bounded byte count. Malformed job and artifact records remain visible as malformed evidence instead of disappearing from listings.

## Audit and observe

Audit events live in a private SQLite WAL ledger. Appends use an immediate transaction and chain each canonical event to the previous hash. Concurrent MCP calls therefore serialize the ledger head without rereading the complete history. `audit_verify` checks the full chain.

The tunnel is registered in `/etc/sinnix/runtime-inventory.json` when enabled. Its workload classification, restartability, and process matcher are part of the same runtime-surface declaration consumed by `sinnix-observe` and machine telemetry. `machine_report` delegates to `sinnix-observe` and bounds the returned JSON.

## NixOS configuration

The local MCP implementation is enabled independently of remote transport:

```nix
sinnix.services.agent-gateway.enable = true;
```

After creating a tunnel and a dedicated runtime key with Read and Use permissions:

```nix
sinnix.services.agent-gateway.tunnel = {
  enable = true;
  tunnelId = "tunnel_...";
  approvedManifestHash = "...";
};
```

The runtime key is the agenix secret `openai-tunnel-runtime-key`. Tunnel-management credentials are not installed in the steady-state service. The pinned `tunnel-client` runs in foreground mode under one systemd user service. Its health, readiness, metrics, and UI endpoint listens on loopback port 3088 by default.

## Deployment and proof

1. Run `switch` so the pinned SDK, tunnel client, generated configuration, runtime inventory, and user units are one generation.
2. Compare `sinnix-agent-gateway-schema remote-readonly` with a direct stdio `tools/list` call.
3. Enable the tunnel only after its ID and dedicated runtime credential exist.
4. Verify `http://127.0.0.1:3088/healthz` and `/readyz`, then inspect the tunnel logs through systemd.
5. Create or refresh the ChatGPT connector from the tunnel, approve the exact read-only tool snapshot, and invoke `gateway_status` plus a bounded project read from ChatGPT.
6. Record the approved manifest hash in the Nix option and compare it during subsequent deployments.

The old prototype state may be retained under the canonical state root's `legacy/` directory for forensic inspection. It must not be loaded as active jobs, artifacts, repositories, tasks, or audit data.
