# Agent gateway

The Sinnix agent gateway is one official-SDK MCP implementation with three explicit authority principals. It exposes canonical project and runtime evidence, forwards typed job requests to `sinnixd`, and keeps transport outside the MCP process.

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
    -> typed sinnixd Unix-socket job.agent.start request
    -> daemon-owned transient service, lifecycle, and bounded artifacts

ChatGPT operator connector
    -> separate OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-mcp --principal operator
    -> explicit operator-authorized tools and attested receipts
```

The gateway owns no HTTP server and no listening port. The official OpenAI tunnel owns the remote connection and launches the MCP server over stdio. The gateway uses the official MCP Python SDK v2 for protocol parsing and typed tool schemas. It retains transport, principal and capability authorization, project authorization, envelopes, audit, and redaction. `sinnixd` owns typed validation, checkout attestation, process and systemd lifecycle, logs, results, cancellation, and reconciliation.

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

`sinnix-agent-gateway-schema` emits a canonical, sorted tool manifest and SHA-256. The selected tunnel principal's manifest is compared with its Nix-approved hash before startup. A local server manifest, an approved Nix manifest, and an externally observed ChatGPT connector snapshot are distinct facts. The private state file `connector-snapshot.json` records an external snapshot with schema `sinnix.gateway-connector-snapshot.v1`, principal, and manifest SHA-256. The gateway reports every comparison as `match`, `mismatch`, or `unobserved`; it does not claim connector parity until an actual product-level observation has been recorded. `status` also exposes the principal contract hash and the principal-filtered action catalog hash separately, so a stable MCP tool manifest cannot conceal a widened action contract.

### V2 contract foundation

Gateway V2 uses the stable verb families `status`, `catalog`, `query`, `get`, `context`, `events`, `wait`, `change`, `operate`, and `run`. Their bindings are validated against the executable action registry at startup: every declared action has one binding whose public verb, owner, and route must match the declaration. `status` calls the gateway observation owner directly and includes non-mutating configured-route preflight evidence. Safe bounded direct routes are invoked and required to satisfy their declared output decoder, while machine observation and Beads remain prerequisite checks because their current owner calls build a whole report before selection or synchronize workspace state. Durable jobs and brokered MCP sessions have distinct lifecycle contracts and are excluded from route preflight. `catalog` searches the V2 registry directly and is distinct from `mcp_catalog`, which remains the registry-derived inventory of upstream MCP brokers. `get` resolves the migrated canonical project, checkout, Beads, task-authority, and bounded job projections. `query` searches a canonical project or checkout reference through the bounded project owner. `context` composes Git and bounded task orientation for a canonical project reference. `events` returns only audit rows visible to the selected principal and binds every row to its canonical receipt reference. `change` is operator-only. It selects declared project, file, Beads, or writable brokered-MCP actions by action name, validates their typed bounded parameters, and preserves idempotency and declared preconditions. File mutations use opaque canonical file references. Beads mutations use canonical project refs and can match an attested task revision. Writable MCP calls use canonical server and tool refs. `operate` selects declared machine, job-cancellation, desktop, terminal, or browser actions by canonical target ref. Machine actions require the owner revision in `preconditions.expected_revision`, forward the idempotency key and reason unchanged, and reject an owner receipt that does not prove the submitted action, target, revision, and key. Job cancellation preserves the daemon's explicit cancellation truth without asserting terminal completion. Desktop control uses `sinnix://desktop/current`; terminal control derives the Kitty matcher from a terminal ref; browser control permits window creation only from the fixed agent-workspace ref and derives later page IDs from registered page refs. `run` selects a typed operator-shell or attested agent job through Sinnixd and returns its canonical job ref. `wait` forwards a bounded long poll for that ref through the same daemon client. Every V2 result retains declared owner/route provenance and an audit receipt, with canonical source refs when an owner response identifies a registered resource. `sinnix://gateway/v2/catalog` remains a principal-filtered MCP resource generated from the same declarations. It publishes canonical templates for project, checkout, bead, job, artifact, receipt, result, machine unit, scope, process, browser page, browser workspace, terminal, desktop, host file, brokered MCP tool, capture lane, session, and context snapshot resources. `project_context`, `project_search`, `audit_tail`, `project_write`, `project_apply_patch`, `machine_action`, `agent_launch`, `job_cancel`, `shell_run`, and `shell_start` are retired because V2 now preserves their owner-domain behavior behind canonical references and bounded envelopes.

`pkgs/sinnix-mcp` is the shared protocol package for the gateway, future `sinnixd` runtime, project adapters, and MCP owners. It owns the canonical `sinnix://` parser and templates, versioned request and response envelopes, bounded inline-or-opaque payload representation, typed errors, source-generation bindings, and a non-overlapping owner registry. Owner declarations name their authority and lifecycle (`read_only`, `daemon_owned`, `window_gated`, or `operator_confirmed`), so an MCP frontend cannot silently widen a domain owner’s write boundary. Archive-backed owners additionally bind returned facts and receipts to their source reference, generation, and root digest.

Fixed direct gateway owners use declared environment profiles rather than the tunnel process environment. Plain routes receive a minimal base environment. Kitty routes additionally require the runtime directory, while Hyprland and screenshot routes also require the Wayland display and Hyprland instance signature. Gateway credentials are never inherited by these child processes. A direct desktop or terminal failure returns its owner route, typed execution facts, and an opaque diagnostic artifact ID. The private artifact contains bounded, redacted stderr evidence but no command arguments or stdout.

The common read surface includes:

- `status`, `catalog`, `machine_report` (the bounded overview), `machine_query`, `capability_search`, and `capability_describe`
- `status`, `catalog`, `query`, `get`, `context`, `events`, `project_list`, `project_tree`, `project_read`, and `project_diff`
- `files_read` for bounded host-path stat, reads, and directory listings
- `session_list`, `session_read`, and `session_search` over authoritative Claude Code and Codex session JSONL files
- `memory_search` and `memory_get` for source-preserving semantic access to available raw coding-session memory
- `timeline_query` for source-preserving coding-session timeline evidence
- `mcp_catalog` and `mcp_read` for registry-derived upstream MCP discovery and explicitly read-only upstream tools
- `capture_lanes` and `capture_query` for runtime-inventory-declared `sinnix-capture` lanes with sidecar indexes
- `desktop_read` for current Hyprland, workspace, client, binding, and color-management state
- `desktop_capture` for output-only screenshots returned as opaque artifacts
- `terminal_read` for Kitty terminal inventory and bounded capture reads
- `browser_read` for Chrome state and bounded page content
- `browser_capture` for screenshots of gateway-created hidden browser targets, returned as opaque artifacts
- `artifact_list` and `artifact_read`
- `audit_verify`

`machine_query` requests one bounded section from the canonical `sinnix-observe` owner. Its operations are `overview`, `pressure`, `runtime_inventory`, `gateway`, `browser`, `storage`, `ingestion`, `units`, `workloads`, `slices`, and `blocked_tasks`; the array operations use cursor and limit pagination. The owner runs only the collectors required for a non-overview section. Every response carries the collector schema, generation time, and observation window. This keeps a large full report from making a small requested section unavailable.

`capability_search` and `capability_describe` read the generated `/etc/sinnix/capability-index.json` rather than maintaining another catalog. Search supports query terms, kind, enabled state, and cursor pagination. Every result identifies the index schema, host, and generation revision. It reports the index as unavailable when the running generation has not rendered it.

`session_list`, `session_read`, and `session_search` read Claude Code sessions from `~/.claude/projects` and Codex sessions from `~/.codex/sessions`. They do not traverse Codex configuration, history, plugin fixtures, or other non-session state. `memory_search` and `memory_get` retain the raw session provider and source-specific reference in every result. They report the current Polylogue and Sinex upstreams as unavailable and Lynchpin as not yet adapted. They do not fabricate a unified source or copy session JSONL into gateway state.

`timeline_query` provides chronological session-file evidence from the same authoritative raw providers. Its timestamps are explicitly identified as filesystem modification times, not inferred conversation-event times. It preserves provider coverage and reports unavailable upstreams instead of treating the available raw files as a complete personal timeline.

`mcp_catalog` is generated from the existing MCP registry and performs a bounded five-second `initialize` plus `tools/list` probe for each admitted stdio upstream when called. It returns the observed availability, total tool count, and explicitly read-only tool count. An unavailable upstream retains its registry row with a typed failure class and, when stderr exists, an opaque diagnostic artifact. The initial broker admits only local evidence servers. It excludes agent control to prevent a recursive job-control path and Chrome DevTools to preserve the browser ownership boundary. `mcp_read` launches a bounded stdio session inside a read-only, network-isolated transient user service for the observer principal, then checks the live upstream tool metadata for an explicit read-only declaration. The child receives the session-bus address because owner-native evidence tools require it, while its filesystem, home, network, and privilege restrictions remain in force. Oversized normalized responses become opaque artifacts. The operator invokes writable tools through `change` with the `mcp.change` action and a canonical brokered-tool ref. Tools that identify themselves as read-only return an explicit unsupported-capability error before invocation.

`operate` is operator-only. It sends one closed typed request to the running ops reducer over its local Unix socket. The canonical target ref is resolved to exactly one owner target, and the request includes the owner-required revision, idempotency key, reason, action, and parameters. The reducer resolves runtime identities, enforces admission, performs the action, and returns its native receipt. The gateway checks that receipt against the submitted action, target, revision, and key. It does not substitute its own service-control path.

`desktop.operate` is operator-only. It delegates exact argument vectors to `sinnix-hypr-control` for focus, dispatcher, shortcut, key-state, paste, and runtime-keyword operations. A focus action returns a newly-read active-window postcondition. It does not provide a session restart or teardown operation. `terminals.operate` delegates exact focus, text send, key send, and command-run vectors to `sinnix-kitty-control` after deriving the matcher from the selected terminal reference. It does not launch untracked coding agents; those continue to use the attested job route. `browser.operate` first creates an agent window from the agent-workspace reference, which the existing wrapper parks on the hidden agent workspace. The gateway persists its returned page ID and allows later navigation, interaction, evaluation, waiting, and closing only against those registered page references. It cannot mutate an existing operator tab. `browser_capture` is read-only, but applies the same registered-target check before Chrome receives a screenshot request, so it cannot capture an existing operator tab. `desktop_capture` invokes only the output capture route and never an interactive area selector or a focus operation.

`agent-control` selects the `agents.run` and `jobs.cancel` V2 actions. `operator` additionally selects the declared change and operate actions. `beads.change` is typed preview/apply: it compiles structural create/update/claim/close/reopen/comment/dependency/relation/reparent/memory/graph-create actions to the configured native owner. Updates append notes by default; replacement requires `patch.notes.mode=replace`. It uses native claim and status/assignee guards where available, labels gateway revision checks as best-effort, rejects stale preview digests before writing, and returns before/after canonical resources, revisions, owner route/version, atomicity mode, and history evidence. The retired generic task operation routers have no executable compatibility path. `files.change` supports atomic replacement, append, mkdir, copy, move, and explicit regular-file removal. Copy and move refuse to replace a destination; moves create the destination before removing the source. A mutation can match the current SHA-256 through `preconditions.expected_sha256`, so concurrent or stale requests fail rather than overwrite newer content. The typed job contract and owner boundary are described below.

## Project and path authority

`sinnix.projects.entries` is the only project registry. It is derived from the existing project paths in `modules/foundation.nix` and rendered into `/etc/sinnix/agent-gateway.json`. `observerRead` controls observer project visibility. It does not govern operator write authority: `operator` receives its project-write capability from its selected principal.

`context` composes a project’s native Git status and latest-commit facts with its native bounded Beads ready-work query. A project without a Beads workspace still returns its Git context and labels the task section unavailable with the next route. It does not parse `.beads/issues.jsonl` or keep a gateway task mirror. `query` accepts only canonical project or checkout refs, so the selected source is explicit in the receipt and result metadata.

Project paths are always relative. Reads and writes reject absolute paths, parent traversal, sensitive path components, and symlink escapes. Tree traversal does not follow symlinks. File reads apply the requested line range before the byte bound, so late ranges do not silently return the beginning of a large file. Git and ripgrep output is written to a temporary file and read back through a fixed response bound instead of being fully buffered in memory.

## Jobs and artifacts

The gateway calls the canonical typed `sinnixd` client for `job.agent.start`, `job.shell.start`, `job.get`, `job.wait`, `job.logs`, `job.result`, and `job.cancel`. V2 `run` selects `shell.run` for the operator or `agents.run` for the agent-control principal. Both paths return the daemon's job ID as a canonical `sinnix://jobs/{job_id}` ref and claim idempotency at the gateway boundary before forwarding. Shell requests do not accept root escalation, environment overlays, commands encoded as strings, or caller-selected units. V2 `wait` is available to every job-reading principal, accepts only a canonical job ref and a 1-300 second bound, and rejects a daemon response carrying a different job ID. `get` reads a bounded canonical job summary, log range, or result. V2 `operate` selects `jobs.cancel` for agent-control and operator, first verifies the requested daemon phase, and returns the owner's `cancel_requested` truth. All responses pass through the common bounded V2 result envelope and retain typed daemon failures.

The daemon derives the environment from the registered project without an overlay, revalidates the exact worktree, common Git directory, porcelain membership, and recorded HEAD immediately before execution, and fails closed on drift. It hands the native runner the canonical registered project path, expected Git common directory, and checkout reference, so the runner independently attests the same worktree before it starts an agent. The daemon's retained transient user service is the only process, cgroup, timeout, and cancellation authority.

Gateway-owned opaque artifacts remain available for non-job owners. Job logs and results are daemon-owned, bounded reads; the gateway does not own their paths, manifests, reservations, PIDs, cgroups, or reconciliation state.

## Audit and observe

Audit events live in a private SQLite WAL ledger. Appends use an immediate transaction and chain each canonical event to the previous hash. Concurrent MCP calls therefore serialize the ledger head without rereading the complete history. `events` is principal-scoped and binds every returned row to `sinnix://receipts/{receipt_id}`. `audit_verify` checks the full chain. The historic hash-chain field is named `profile` for compatibility, but its values are current principal names and returned events expose `principal`.

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
5. Create or refresh the ChatGPT connector from the tunnel, approve its exact tool snapshot, and invoke `status`, `catalog`, and a bounded project read from ChatGPT.
6. Record the observed connector tool names and manifest hash separately from the Nix-approved manifest. The observation is required before claiming connector parity.

The old prototype state may be retained under the canonical state root's `legacy/` directory for forensic inspection. It must not be loaded as active jobs, artifacts, repositories, tasks, or audit data.
