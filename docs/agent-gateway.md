# Agent gateway

The Sinnix agent gateway is one official-SDK MCP implementation with three explicit authority principals. It exposes canonical project and runtime evidence, reuses the attested transient-systemd agent substrate, and keeps transport outside the MCP process.

## Architecture

```text
ChatGPT observer connector
    -> OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-mcp --principal observer
    -> shared project, job, artifact, audit, and observe services

Local coordinators
    -> sinnix-agent-control-mcp
    -> stdio: sinnix-agent-gateway --principal agent-control
    -> run_agent_prompt.sh and agent_job_control.sh
    -> transient systemd scope, manifest, cgroup, and bounded artifacts

ChatGPT operator connector
    -> separate OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-mcp --principal operator
    -> explicit operator-authorized tools and attested receipts
```

The gateway owns no HTTP server and no listening port. The official OpenAI tunnel owns the remote connection and launches the MCP server over stdio. The gateway uses the official MCP Python SDK v2 for protocol parsing and typed tool schemas.

## Principals

| Principal | Intended caller | Read projects, jobs, artifacts, audit, machine | Launch and cancel jobs | Write projects |
| --- | --- | --- | --- | --- |
| `observer` | Read-only ChatGPT connector and local inspection | Yes, for projects that opt into `observerRead` | No | No |
| `agent-control` | Trusted local coordinators | Yes | Yes | No |
| `operator` | Local testing and a write-capable remote workspace | Yes | Yes | Yes |

Tool registration follows the principal. A denied capability is absent from `tools/list`, and the underlying service enforces the same capability again. `observer` therefore cannot obtain a write path by calling an unlisted function directly.

Authority and transport are independent. A tunnel selects its principal explicitly through `sinnix.services.agent-gateway.tunnel.principal`; a remote connection does not narrow or expand the selected authority. The observer transport remains sandboxed. The operator transport must not impose a sandbox policy that contradicts the selected operator authority.

Ordinary full and browser agent profiles do not receive `agent-control`. Explicit orchestration profiles do. This keeps process mutation out of broad always-on tool surfaces.

## Interfaces

The configured commands are:

```bash
sinnix-agent-gateway-mcp --principal observer
sinnix-agent-control-mcp
sinnix-agent-gateway-schema observer
sinnix-agent-gateway --config /etc/sinnix/agent-gateway.json --principal observer info
```

`sinnix-agent-gateway-schema` emits a canonical, sorted tool manifest and SHA-256. The selected tunnel principal's manifest is compared with its Nix-approved hash before startup. A local server manifest, an approved Nix manifest, and an externally observed ChatGPT connector snapshot are distinct facts. The private state file `connector-snapshot.json` records an external snapshot with schema `sinnix.gateway-connector-snapshot.v1`, principal, and manifest SHA-256. The gateway reports every comparison as `match`, `mismatch`, or `unobserved`; it does not claim connector parity until an actual product-level observation has been recorded.

The common read surface includes:

- `gateway_status`, `machine_report`, `machine_query`, `capability_search`, and `capability_describe`
- `project_list`, `project_tree`, `project_read`, `project_search`, and `project_diff`
- `files_read` for bounded host-path stat, reads, and directory listings
- `session_list`, `session_read`, and `session_search` over authoritative Claude Code and Codex JSONL files
- `shell_query` for exact-argument, output-bounded read-only host inspection
- `shell_run` for exact-argument operator commands in an unrestricted transient user service, with explicit optional `sudo -n` root execution
- `desktop_read` for current Hyprland, workspace, client, binding, and color-management state
- `terminal_read` for Kitty terminal inventory and bounded capture reads
- `browser_read` for Chrome state and bounded page content
- `job_list`, `job_status`, and `job_read_output`
- `artifact_list` and `artifact_read`
- `audit_tail` and `audit_verify`

`machine_query` selects one bounded section from the canonical `sinnix-observe` report. Its operations are `overview`, `pressure`, `runtime_inventory`, `gateway`, `browser`, `storage`, `ingestion`, `units`, `workloads`, `slices`, and `blocked_tasks`; the array operations use cursor and limit pagination. Every response carries the collector schema, generation time, and observation window. This keeps a large full report from making a small requested section unavailable.

`capability_search` and `capability_describe` read the generated `/etc/sinnix/capability-index.json` rather than maintaining another catalog. Search supports query terms, kind, enabled state, and cursor pagination. Every result identifies the index schema, host, and generation revision. It reports the index as unavailable when the running generation has not rendered it.

`machine_action` is operator-only. It sends the complete typed request to the running ops reducer over its local Unix socket, including the owner-required revision, idempotency key, reason, target, and parameters. The reducer resolves runtime identities, enforces admission, performs the action, and returns its native receipt. The gateway does not substitute its own service-control path.

`desktop_action` is operator-only. It delegates exact argument vectors to `sinnix-hypr-control` for focus, dispatcher, shortcut, key-state, paste, and runtime-keyword operations. A focus action returns a newly-read active-window postcondition. It does not provide a session restart or teardown operation.

`terminal_action` is operator-only. It delegates exact focus, text send, key send, and command-run vectors to `sinnix-kitty-control` against an explicit Kitty matcher. It does not launch untracked coding agents; those continue to use the attested job route.

`browser_action` is operator-only. It first creates an agent window, which the existing wrapper parks on the hidden agent workspace. The gateway persists its returned page ID and allows later navigation, interaction, evaluation, waiting, and closing only against those registered agent targets. It cannot mutate an existing operator tab.

`agent-control` adds `agent_launch` and `job_cancel`. `operator` also adds `files_write`, `project_write`, `project_apply_patch`, `shell_run`, and `shell_start`. `shell_run` accepts exact argv, a working directory, bounded environment overlay, timeout, output limit, and an explicit root flag. It uses `env -i` and a bounded base environment, then invokes `sudo -n --` only when root was requested. The returned receipt identifies the transient service unit, selected identity, exit status, timeout, and output-truncation facts. `shell_start` uses the existing agent-slice scope policy to create a durable, attested shell job. It returns a stable job ID and scope unit; `job_status`, `job_read_output`, and `job_cancel` use that identity rather than a PID. `files_write` supports atomic replacement, append, mkdir, and explicit regular-file removal. A mutation can require the current SHA-256 so concurrent or stale requests fail rather than overwrite newer content.

## Project and path authority

`sinnix.projects.entries` is the only project registry. It is derived from the existing project paths in `modules/foundation.nix` and rendered into `/etc/sinnix/agent-gateway.json`. `observerRead` controls observer project visibility. It does not govern operator write authority: `operator` receives its project-write capability from its selected principal.

Project paths are always relative. Reads and writes reject absolute paths, parent traversal, sensitive path components, and symlink escapes. Tree traversal does not follow symlinks. File reads apply the requested line range before the byte bound, so late ranges do not silently return the beginning of a large file. Git and ripgrep output is written to a temporary file and read back through a fixed response bound instead of being fully buffered in memory.

## Jobs and artifacts

The gateway does not implement another job runner. `agent_launch` calls the shared `run_agent_prompt.sh`, which creates a transient systemd scope and a versioned manifest containing the stable job ID, cgroup, unit, worktree, prompt digest, resource overrides, timeout, lifecycle, and artifact locations. `RuntimeMaxSec` enforces the declared timeout. Cancellation accepts only an attested job ID and verifies the unit, PID, cgroup, and working directory before stopping the scope.

Only an explicit environment allowlist reaches launched agents. Unrelated exported secrets are not inherited. Job state and generated prompt, manifest, log, and artifact metadata are private to the user.

Artifacts use random opaque UUIDs. The public metadata omits host paths, and reads use offset plus a bounded byte count. Malformed job and artifact records remain visible as malformed evidence instead of disappearing from listings.

## Audit and observe

Audit events live in a private SQLite WAL ledger. Appends use an immediate transaction and chain each canonical event to the previous hash. Concurrent MCP calls therefore serialize the ledger head without rereading the complete history. `audit_verify` checks the full chain. The historic hash-chain field is named `profile` for compatibility, but its values are current principal names and returned events expose `principal`.

The tunnel is registered in `/etc/sinnix/runtime-inventory.json` when enabled. Its workload classification, restartability, and process matcher are part of the same runtime-surface declaration consumed by `sinnix-observe` and machine telemetry. `machine_report` delegates to `sinnix-observe` and bounds the returned JSON.

## NixOS configuration

The local MCP implementation is enabled independently of remote transport:

```nix
sinnix.services.agent-gateway.enable = true;
```

After creating a tunnel and a dedicated runtime key with the required permissions:

```nix
sinnix.services.agent-gateway.tunnel = {
  enable = true;
  principal = "observer";
  tunnelId = "tunnel_...";
  approvedManifestHash = "...";
};
```

The runtime key is the agenix secret `openai-tunnel-runtime-key`. Tunnel-management credentials are not installed in the steady-state service. The pinned `tunnel-client` runs in foreground mode under one systemd user service. Its health, readiness, metrics, and UI endpoint listens on loopback port 3088 by default.

## Deployment and proof

1. Run `switch` so the pinned SDK, tunnel client, generated configuration, runtime inventory, and user units are one generation.
2. Compare `sinnix-agent-gateway-schema observer` with a direct stdio `tools/list` call.
3. Enable a tunnel only after its ID and dedicated runtime credential exist.
4. Verify `http://127.0.0.1:3088/healthz` and `/readyz`, then inspect the tunnel logs through systemd.
5. Create or refresh the ChatGPT connector from the tunnel, approve its exact tool snapshot, and invoke `gateway_status` plus a bounded project read from ChatGPT.
6. Record the observed connector tool names and manifest hash separately from the Nix-approved manifest. The observation is required before claiming connector parity.

The old prototype state may be retained under the canonical state root's `legacy/` directory for forensic inspection. It must not be loaded as active jobs, artifacts, repositories, tasks, or audit data.
