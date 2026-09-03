# Agent gateway

The Sinnix agent gateway is one official-SDK MCP implementation with three explicit authority principals. It exposes canonical project and runtime evidence, queues jobs through agentctl in process, and keeps transport outside the MCP process.

## Architecture

```text
ChatGPT observer connector
    -> OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-observer-mcp
    -> shared project, job, artifact, audit, and observe services

Local coordinators
    -> sinnix-agent-control-mcp
    -> stdio: sinnix-agent-gateway --principal agent-control
    -> agentctl's launch and lane routes, in process
    -> a pueue task, its log and typed result

ChatGPT operator connector
    -> separate OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-operator-mcp
    -> explicit operator-authorized tools and attested receipts
```

The gateway owns no HTTP server and no listening port. The official OpenAI tunnel owns the remote connection and launches the MCP server over stdio. The gateway uses the official MCP Python SDK v2 for protocol parsing and typed tool schemas. It retains transport, principal and capability authorization, project authorization, envelopes, audit, and redaction. Jobs are pueue tasks: agentctl (`docs/sinnixd.md`) owns the launch input, the pool, the log and typed result, and cancellation; the gateway calls its launch and lane routes in process and implements no second job controller.

## Principals

| Principal       | Intended caller                                    | Read projects, jobs, artifacts, audit, machine | Launch and cancel jobs | Write projects |
| --------------- | -------------------------------------------------- | ---------------------------------------------- | ---------------------- | -------------- |
| `observer`      | Read-only ChatGPT connector and local inspection   | Yes, for projects that opt into `observerRead` | No                     | No             |
| `agent-control` | Trusted local coordinators                         | Yes                                            | Yes                    | No             |
| `operator`      | Local testing and a write-capable remote workspace | Yes                                            | Yes                    | Yes            |

The ten protocol verb names remain stable in `tools/list` for every principal. The principal-filtered catalog omits unauthorized actions, and direct calls to an effectful verb fail with `policy_denied` before any owner callback is dispatched. The underlying service enforces the same capability again. `observer` therefore cannot obtain a write path through `change`, `operate`, or `run`.

Authority and transport are independent. Each `sinnix.services.agent-gateway.endpoints.<name>` entry selects its principal explicitly; a remote connection does not narrow or expand the selected authority. The observer transport remains sandboxed. The operator transport must not impose a sandbox policy that contradicts the selected operator authority.

Ordinary full and browser agent profiles do not receive `agent-control`. Explicit orchestration profiles do. This keeps process mutation out of broad always-on tool surfaces.

## Interfaces

The configured commands are:

```bash
sinnix-agent-gateway-observer-mcp
sinnix-agent-control-mcp
sinnix-agent-gateway-observer-schema
sinnix-agent-gateway --principal agent-control info
sinnix-agent-gateway --config /etc/sinnix/agent-gateway-observer.json --principal observer info
```

The bare local CLI and `agent-control` wrapper default to the generated `/etc/sinnix/agent-gateway.json`, which contains all registered projects and the same declared owner command paths as remote endpoint configs. `--config` and `SINNIX_AGENT_GATEWAY_CONFIG` remain explicit overrides. The local config has no tunnel or publication approval state because it is a local stdio principal.

Each endpoint-specific schema command emits a canonical, sorted tool manifest and SHA-256. The endpoint's selected principal manifest is compared with its Nix-approved hash before startup. A local server manifest, an approved Nix manifest, and an externally observed ChatGPT connector snapshot are distinct facts. The private state file `connector-snapshot.json` records an external snapshot with schema `sinnix.gateway-connector-snapshot.v1`, principal, and manifest SHA-256. The gateway reports every comparison as `match`, `mismatch`, or `unobserved`; it does not claim connector parity until an actual product-level observation has been recorded. `status` also exposes the principal contract hash and the principal-filtered action catalog hash separately, so a stable MCP tool manifest cannot conceal a widened action contract.

### V2 contract foundation

Gateway V2 exposes ten stable verbs: `status`, `catalog`, `query`, `get`, `context`, `events`, `wait`, `change`, `operate`, and `run`. The operator manifest contains exactly those names. Bindings are generated from the executable action registry, so every action declares one public verb, owner, and typed `OwnerRoute`; the route is the dispatch authority and the action name is only its catalog selector. `catalog` filters the registry for the selected principal and links each action to its lazy schema resource. `query` is the compact read surface for declared project, machine, capability, MCP broker, desktop, terminal, browser, host-file, session, memory, timeline, artifact, audit, capture, and job-list routes. `get` round-trips canonical project, checkout, Beads, task-authority, job, artifact, receipt, result, machine-unit, registered browser page, terminal, desktop, host-file, capture-lane, capability, and session resources through their existing owners. `context`, `events`, and `wait` keep their bounded project, receipt, and job contracts. `jobs.query` passes its requested limit to the job owner, which returns bounded rows plus total and truncation metadata. `agent.for_bead` starts a lane for a canonical Beads ref: agentctl compiles the prompt from the bead, creates the worktree and queues the agent; backend, model and effort default to the bead's model policy. `machine.query` exposes owner-selected overview and entity sections with cursor continuation. V2 has no read-only shell path, only the operator's queued shell command.

`change`, `operate`, and `run` are effectful and remain separately annotated. `change` selects declared project, file, Beads, or writable brokered-MCP actions. `operate` selects declared machine, Beads-maintenance, job-cancellation, desktop, terminal, or browser actions. `run` queues an operator shell command, a declared operation, or a lane agent. Effectful requests preserve preconditions, idempotency, receipts, owner route provenance, and canonical source references. The action catalog hash is approved independently from the tool manifest hash, so a stable ten-verb manifest cannot conceal an authority change.

### g2.10 context, events, waits, and prompts

The existing `context`, `events`, `wait`, `get`, and `run` verbs carry the g2.10 surfaces. Context intents are `project.orientation`, `project.triage`, `job.review`, and `incident`. Each intent declares a bounded component plan. Components report available or unavailable state, an owner source revision when available, and one immutable context snapshot reference. Components are isolated, and the bounded ephemeral gateway revision cache reuses a value only when the owner revision is identical. The gateway atomically persists the 64 most recently used content-addressed snapshots per principal under its existing state root, so refs survive process restart without introducing a daemon or materialization store.

`events` normalizes existing gateway audit receipts, job observations, ops-reducer transitions, Beads owner revisions, and Git project revisions. Exact events retain their owner evidence. Revision observations are explicitly non-exact and do not claim an event that the owner did not provide. Continuations are authenticated opaque cursors bound to the principal and a scope of at most 16 projects, keyed from the private persisted gateway cursor secret. The project bound leaves room for both Git and Beads revisions inside the 4 KiB cursor contract. Cursor state is bounded independently of job population, and positions advance only for rows included in a response.

`wait` supports job terminal state, Beads status or revision, unit state, file hash, capture freshness, and receipt appearance. It polls asynchronously within a maximum deadline and observes the actual MCP request cancellation event. A timeout or cancellation returns current evidence and an opaque continuation. It never submits background work. Canonical resource templates are principal-filtered and paginated by an opaque cursor keyed from the same private gateway secret. The gateway's owner-revision publisher runs from server lifespan and publishes resource updates after idle owner observations change, never as a side effect of a response. The four generated prompts are `orient-project`, `triage-beads`, `review-job`, and `incident-orient`. They contain canonical refs and the same principal-filtered action catalog, but do not invoke actions or grant authority.

The catalog publishes canonical templates for project, checkout, bead, job, artifact, receipt, result, machine unit, process, browser page, browser workspace, terminal, desktop, host file, brokered MCP tool, capture lane, capability, session, and context snapshot resources.

For machine effectors, `machine.query` with `operation=actions` reads the ops reducer's bounded authoritative revision endpoint. A cold client combines that revision with a canonical target from the ordinary machine query/get routes when calling `machine.operate`; it does not need direct reducer-socket access, the reducer's potentially large full snapshot, or a guessed precondition.

`beads.changeset` is an operator-only `change` action. It previews or applies a bounded ordered list of existing typed Beads mutations. Each action carries its canonical project or bead reference and may bind a newly created bead with `bind`. A later action refers to that bead as `$bind`. Bindings cannot cross project partitions, and canonical cross-project Beads references are rejected before any mutation. The preview contains the source revision for every project, a digest, partitions, planned compensation hints, and its truthful atomicity: `owner_atomic` only for one owner-validated `bd create --graph` action, `per_step_commits` for ordinary work in one project, or `cross_project_partitioned` for work spanning projects. Apply reports every action as `applied`, `failed`, or `skipped`; `on_error` is explicitly `stop` or `continue`. A changeset never calls a shared-server batch API, rolls back a prior step, claims unrelated writer changes, or creates hidden cross-project edges.

Ordinary Beads mutations remain Dolt-only. They do not export `issues.jsonl` and do not create Git bookkeeping commits. `beads.operate` is the separate operator-only route for `snapshot.publish`, `sync.push`, `sync.pull`, `backup.create`, `backup.list`, and `backup.restore`. Snapshot publication writes a deterministic gateway-owned export, returns before and after SHA-256 values plus a bounded unified diff, and still performs no Git commit. Sync uses the owner-native Dolt push or pull command. Backup commands are limited to the pinned owner's declared backup operations.

`pkgs/sinnix-mcp` is the shared protocol package for the gateway, future `sinnixd` runtime, project adapters, and MCP owners. It owns the canonical `sinnix://` parser and templates, versioned request and response envelopes, bounded inline-or-opaque payload representation, typed errors, source-generation bindings, and a non-overlapping owner registry. Owner declarations name their authority and lifecycle (`read_only`, `daemon_owned`, `window_gated`, or `operator_confirmed`), so an MCP frontend cannot silently widen a domain owner’s write boundary. Archive-backed owners additionally bind returned facts and receipts to their source reference, generation, and root digest.

Fixed direct gateway owners use declared environment profiles rather than the tunnel process environment. Plain routes receive a minimal base environment. Kitty routes additionally require the runtime directory, while Hyprland and screenshot routes also require the Wayland display and Hyprland instance signature. Gateway credentials are never inherited by these child processes. A direct desktop or terminal failure returns its owner route, typed execution facts, and an opaque diagnostic artifact ID. The private artifact contains bounded, redacted stderr evidence but no command arguments or stdout.

The read actions retain each owner’s existing bounds and authority checks. `machine.query` selects one `sinnix-observe` section rather than building a whole-machine response; array sections retain cursor paging, aggregate sections fall back to attested artifacts, and the common V2 envelope artifactizes any oversized owner payload. `mcp.query` exposes every admitted upstream tool's real namespaced ref, input schema, and read/change effect. A read invocation names that canonical tool ref instead of a public server/tool argument bag. Observer MCP catalog and call routes require the healthy user-session bus environment; missing session variables are reported unavailable before an upstream launch. Oversized MCP schemas and catalogs are retained as attested JSON artifacts with bounded catalog metadata, and oversized gateway contract resources use the same artifact form. Desktop, terminal, and browser owner failures retain exact diagnostic artifact refs in the typed error envelope. `captures.query` derives every declared lane's exact path and native contract from runtime inventory: an admitted sidecar lane uses its path basename and parent root, while file-backed or other owner-native paths remain visible with an explicit unavailable reader rather than a guessed query. Session, memory, timeline, file, UI, project, artifact, capability, and audit queries retain their source provenance and bounded pagination behind their declared action schemas. Targeted desktop, terminal, browser, and host-file reads require their canonical resource refs; only collection operations such as browser tab listing and terminal listing omit a target.

`operate` is operator-only. It sends one closed typed request to the running ops reducer over its local Unix socket. The canonical target ref is resolved to exactly one owner target, and the request includes the owner-required revision, idempotency key, reason, action, and parameters. The reducer resolves runtime identities, enforces admission, performs the action, and returns its native receipt. The gateway checks that receipt against the submitted action, target, revision, and key. It does not substitute its own service-control path.

`desktop.operate` is operator-only. It delegates exact argument vectors to `sinnix-hypr-control` for focus, dispatcher, shortcut, key-state, paste, and runtime-keyword operations. A focus action returns a newly-read active-window postcondition. It does not provide a session restart or teardown operation. `terminals.operate` delegates exact focus, text send, key send, and command-run vectors to `sinnix-kitty-control` after deriving the matcher from the selected terminal reference. It does not launch untracked coding agents; those continue to use the attested job route. `browser.operate` first creates an agent window from the agent-workspace reference, which the existing wrapper parks on the hidden agent workspace. The gateway persists its returned page ID and allows later navigation, interaction, evaluation, waiting, and closing only against those registered page references. It cannot mutate an existing operator tab. `browser.query` capture applies the same registered-target check before Chrome receives a screenshot request, so it cannot capture an existing operator tab. Desktop capture invokes only the output capture route and never an interactive area selector or a focus operation.

`agent-control` reads Beads like the other principals and may start and cancel jobs; it cannot write projects, files, Beads, or the desktop. `beads.change` is typed preview/apply: it compiles structural create/update/claim/close/reopen/comment/dependency/relation/reparent/memory/graph-create actions to the configured native owner. A lane's bead is closed by `agentctl lane sync` once its pull request merges, not by the gateway. Updates append notes by default; replacement requires `patch.notes.mode=replace`. The retired generic task operation routers have no executable compatibility path. `files.change` supports atomic replacement, append, mkdir, copy, move, and explicit regular-file removal. Copy and move refuse to replace a destination; moves create the destination before removing the source. A mutation can match the current SHA-256 through `preconditions.expected_sha256`, so concurrent or stale requests fail rather than overwrite newer content. The typed job contract and owner boundary are described below.

## Project and path authority

`sinnix.projects.entries` is the only project registry. It is derived from the existing project paths in `modules/foundation.nix` and filtered into each `/etc/sinnix/agent-gateway-<endpoint>.json` according to that endpoint's project scope. `observerRead` controls observer project visibility. It does not govern operator write authority: `operator` receives its project-write capability from its selected principal.

`context` composes a project’s native Git status and latest-commit facts with its native bounded Beads ready-work query. A project without a Beads workspace still returns its Git context and labels the task section unavailable with the next route. It does not parse `.beads/issues.jsonl` or keep a gateway task mirror. `query` accepts only canonical project or checkout refs, so the selected source is explicit in the receipt and result metadata.

Project paths are always relative. Reads and writes reject absolute paths, parent traversal, sensitive path components, and symlink escapes. Tree traversal does not follow symlinks. File reads apply the requested line range before the byte bound, so late ranges do not silently return the beginning of a large file. Git and ripgrep output is written to a temporary file and read back through a fixed response bound instead of being fully buffered in memory.

## Jobs and artifacts

The job owner (`sinnix_agent_gateway/execution.py`) dispatches `job.start`, `job.agent.start`, `job.shell.start`, `job.get`, `job.wait`, `job.logs`, `job.result`, `job.list`, and `job.cancel` onto agentctl's launch and lane routes in process. A job's identity is its pueue task id; its state is pueue's phase, terminal flag and exit code. `run(action_name=operations.run)` queues a declared operation on the main checkout or a worktree. `run(action_name=agent.for_bead)` is `agentctl lane start`. `run(action_name=shell.run)` queues one argv in the `interactive` pool inside the project's declared environment, with its working directory confined to the checkout; it accepts no root escalation, environment overlay, string-encoded command, or caller-selected unit. `context(intent=job.review)` returns the job, its typed result, its project and recent receipts. V2 `wait` is available to every job-reading principal, accepts only a canonical job ref and a 1-300 second bound, and rejects an owner response carrying a different job ID. `get` reads a bounded canonical job summary, log range, or result. V2 `operate` selects `jobs.cancel` for agent-control and operator, first verifies the requested phase, and returns the queue's `cancel_requested` answer. All responses pass through the common bounded V2 result envelope and retain typed owner failures.

Gateway-owned opaque artifacts remain available for non-job owners and are scoped to their creating principal; `operator` may read all artifacts, while observer and agent-control may read only their own. Job logs and results are agentctl's bounded artifacts; the gateway does not own their paths, PIDs, cgroups, or timeouts.

## Audit and observe

Audit events live in a private SQLite WAL ledger. Appends use an immediate transaction and chain each canonical event to the previous hash. Concurrent MCP calls therefore serialize the ledger head without rereading the complete history. Every V2 call, including logical reads, appends an audit receipt and persists an immutable result snapshot. This bounded observability persistence is declared in each action contract, so logical read verbs are not annotated `readOnlyHint=true`; their owner effect remains read-only while the MCP call truthfully has a local audit/result side effect. `events` is principal-scoped and binds every returned row to `sinnix://receipts/{receipt_id}`. The `audit.verify` action checks the full chain. The historic hash-chain field is named `profile` for compatibility, but its values are current principal names and returned events expose `principal`.

The tunnel is registered in `/etc/sinnix/runtime-inventory.json` when enabled. Its workload classification, restartability, and process matcher are part of the same runtime-surface declaration consumed by `sinnix-observe` and machine telemetry. `machine.query` delegates to `sinnix-observe` and bounds the selected JSON section.

## NixOS configuration

The local MCP implementation is enabled independently of remote transport:

```nix
sinnix.services.agent-gateway.enable = true;
```

After creating a tunnel and a dedicated runtime key with the required permissions:

```nix
sinnix.services.agent-gateway.endpoints.operator = {
  enable = true;
  principal = "operator";
  tunnelId = "tunnel_...";
  runtimeKeyFile = "/run/agenix/openai-tunnel-runtime-key";
  approvedManifestHash = "...";
  approvedActionCatalogHash = "...";
};
```

The private operator runtime key is the agenix secret `openai-tunnel-runtime-key`. Tunnel-management credentials are not installed in the steady-state service. Every enabled endpoint receives its own generated config, MCP wrapper, approval gate, state directory, runtime credential, health port, systemd user service, and runtime surface. Prime enables the private operator endpoint on loopback port 3088. A separately credentialed observer endpoint remains optional for deliberately constrained sharing.

## Deployment and proof

1. Provision the endpoint's tunnel ID and dedicated runtime credential. Keep an operator credential limited to its authenticated private tunnel.
2. Run `switch` so the pinned SDK, tunnel client, endpoint configs, runtime inventory, and user units are one generation.
3. Compare each enabled endpoint's schema command with a direct stdio `tools/list` call. Every manifest retains the stable ten verb names; principal-filtered catalogs and runtime authorization exclude observer mutation authority.
4. Verify the enabled endpoint's `/healthz` and `/readyz` paths on its configured loopback health port, then inspect that endpoint's tunnel log through systemd.
5. Create or refresh the ChatGPT connector from that endpoint's tunnel, approve its exact tool snapshot, and invoke `status`, `catalog`, and a bounded project read.
6. Record observed connector tool names and manifest hash for each enabled endpoint. This observation is required before claiming connector parity. Repeat the proof independently when the operator endpoint is provisioned and enabled.
<!-- BEGIN GENERATED GATEWAY V2 REFERENCE -->

## Generated V2 reference

This section is generated from the canonical gateway registry. Revision `v2-g3.0-pueue-jobs`, catalog SHA-256 `885e3a2cee22a5488d8cc0dd289312bb9105a7f9679c8a247afeda5dbb919548`.

The full schemas and executable examples are in [the generated gateway reference](generated/agent-gateway-reference.md). The matching agent skill is [agent-gateway](../dots/_ai/skills/agent-gateway/SKILL.md).

| Action               | Verb      | Owner              | Route                     | Schema                                                                                             |
| -------------------- | --------- | ------------------ | ------------------------- | -------------------------------------------------------------------------------------------------- |
| `gateway.status`     | `status`  | `gateway`          | `observe.gateway_status`  | [`sinnix://gateway/v2/actions/gateway.status`](sinnix://gateway/v2/actions/gateway.status)         |
| `gateway.catalog`    | `catalog` | `registry`         | `registry.search`         | [`sinnix://gateway/v2/actions/gateway.catalog`](sinnix://gateway/v2/actions/gateway.catalog)       |
| `resources.get`      | `get`     | `resolver`         | `resources.get`           | [`sinnix://gateway/v2/actions/resources.get`](sinnix://gateway/v2/actions/resources.get)           |
| `projects.query`     | `query`   | `projects`         | `projects.search`         | [`sinnix://gateway/v2/actions/projects.query`](sinnix://gateway/v2/actions/projects.query)         |
| `beads.query`        | `query`   | `beads`            | `beads.query`             | [`sinnix://gateway/v2/actions/beads.query`](sinnix://gateway/v2/actions/beads.query)               |
| `projects.context`   | `context` | `project-context`  | `project_context.context` | [`sinnix://gateway/v2/actions/projects.context`](sinnix://gateway/v2/actions/projects.context)     |
| `audit.events`       | `events`  | `audit`            | `audit.tail`              | [`sinnix://gateway/v2/actions/audit.events`](sinnix://gateway/v2/actions/audit.events)             |
| `jobs.wait`          | `wait`    | `systemd-jobs`     | `job.wait`                | [`sinnix://gateway/v2/actions/jobs.wait`](sinnix://gateway/v2/actions/jobs.wait)                   |
| `projects.change`    | `change`  | `projects`         | `projects.change`         | [`sinnix://gateway/v2/actions/projects.change`](sinnix://gateway/v2/actions/projects.change)       |
| `files.change`       | `change`  | `files`            | `files.change`            | [`sinnix://gateway/v2/actions/files.change`](sinnix://gateway/v2/actions/files.change)             |
| `beads.change`       | `change`  | `beads`            | `beads.write`             | [`sinnix://gateway/v2/actions/beads.change`](sinnix://gateway/v2/actions/beads.change)             |
| `beads.changeset`    | `change`  | `beads`            | `beads.changeset`         | [`sinnix://gateway/v2/actions/beads.changeset`](sinnix://gateway/v2/actions/beads.changeset)       |
| `beads.operate`      | `operate` | `beads`            | `beads.maintenance`       | [`sinnix://gateway/v2/actions/beads.operate`](sinnix://gateway/v2/actions/beads.operate)           |
| `mcp.change`         | `change`  | `mcp-broker`       | `mcp.call.write`          | [`sinnix://gateway/v2/actions/mcp.change`](sinnix://gateway/v2/actions/mcp.change)                 |
| `machine.operate`    | `operate` | `ops-reducer`      | `ops.actions.execute`     | [`sinnix://gateway/v2/actions/machine.operate`](sinnix://gateway/v2/actions/machine.operate)       |
| `operations.run`     | `run`     | `systemd-jobs`     | `job.start`               | [`sinnix://gateway/v2/actions/operations.run`](sinnix://gateway/v2/actions/operations.run)         |
| `agent.for_bead`     | `run`     | `systemd-jobs`     | `job.agent.start`         | [`sinnix://gateway/v2/actions/agent.for_bead`](sinnix://gateway/v2/actions/agent.for_bead)         |
| `jobs.cancel`        | `operate` | `systemd-jobs`     | `job.cancel`              | [`sinnix://gateway/v2/actions/jobs.cancel`](sinnix://gateway/v2/actions/jobs.cancel)               |
| `desktop.operate`    | `operate` | `desktop`          | `desktop.action`          | [`sinnix://gateway/v2/actions/desktop.operate`](sinnix://gateway/v2/actions/desktop.operate)       |
| `terminals.operate`  | `operate` | `terminals`        | `terminals.action`        | [`sinnix://gateway/v2/actions/terminals.operate`](sinnix://gateway/v2/actions/terminals.operate)   |
| `browser.operate`    | `operate` | `browser`          | `browser.action`          | [`sinnix://gateway/v2/actions/browser.operate`](sinnix://gateway/v2/actions/browser.operate)       |
| `shell.run`          | `run`     | `systemd-jobs`     | `job.shell.start`         | [`sinnix://gateway/v2/actions/shell.run`](sinnix://gateway/v2/actions/shell.run)                   |
| `projects.list`      | `query`   | `projects`         | `projects.list`           | [`sinnix://gateway/v2/actions/projects.list`](sinnix://gateway/v2/actions/projects.list)           |
| `projects.tree`      | `query`   | `projects`         | `projects.tree`           | [`sinnix://gateway/v2/actions/projects.tree`](sinnix://gateway/v2/actions/projects.tree)           |
| `projects.read`      | `query`   | `projects`         | `projects.read`           | [`sinnix://gateway/v2/actions/projects.read`](sinnix://gateway/v2/actions/projects.read)           |
| `projects.diff`      | `query`   | `projects`         | `projects.diff`           | [`sinnix://gateway/v2/actions/projects.diff`](sinnix://gateway/v2/actions/projects.diff)           |
| `machine.query`      | `query`   | `machine`          | `observe.machine_query`   | [`sinnix://gateway/v2/actions/machine.query`](sinnix://gateway/v2/actions/machine.query)           |
| `capabilities.query` | `query`   | `capability-index` | `capability_index.query`  | [`sinnix://gateway/v2/actions/capabilities.query`](sinnix://gateway/v2/actions/capabilities.query) |
| `mcp.query`          | `query`   | `mcp-broker`       | `mcp.call.read`           | [`sinnix://gateway/v2/actions/mcp.query`](sinnix://gateway/v2/actions/mcp.query)                   |
| `desktop.query`      | `query`   | `desktop`          | `desktop.read`            | [`sinnix://gateway/v2/actions/desktop.query`](sinnix://gateway/v2/actions/desktop.query)           |
| `terminals.query`    | `query`   | `terminals`        | `terminals.read`          | [`sinnix://gateway/v2/actions/terminals.query`](sinnix://gateway/v2/actions/terminals.query)       |
| `browser.query`      | `query`   | `browser`          | `browser.read`            | [`sinnix://gateway/v2/actions/browser.query`](sinnix://gateway/v2/actions/browser.query)           |
| `files.query`        | `query`   | `files`            | `files.read`              | [`sinnix://gateway/v2/actions/files.query`](sinnix://gateway/v2/actions/files.query)               |
| `sessions.query`     | `query`   | `sessions`         | `sessions.query`          | [`sinnix://gateway/v2/actions/sessions.query`](sinnix://gateway/v2/actions/sessions.query)         |
| `memory.query`       | `query`   | `memory`           | `memory.query`            | [`sinnix://gateway/v2/actions/memory.query`](sinnix://gateway/v2/actions/memory.query)             |
| `timeline.query`     | `query`   | `timeline`         | `timeline.query`          | [`sinnix://gateway/v2/actions/timeline.query`](sinnix://gateway/v2/actions/timeline.query)         |
| `artifacts.query`    | `query`   | `artifacts`        | `artifacts.query`         | [`sinnix://gateway/v2/actions/artifacts.query`](sinnix://gateway/v2/actions/artifacts.query)       |
| `audit.verify`       | `query`   | `audit`            | `audit.verify`            | [`sinnix://gateway/v2/actions/audit.verify`](sinnix://gateway/v2/actions/audit.verify)             |
| `captures.query`     | `query`   | `captures`         | `captures.query`          | [`sinnix://gateway/v2/actions/captures.query`](sinnix://gateway/v2/actions/captures.query)         |
| `jobs.query`         | `query`   | `systemd-jobs`     | `job.list`                | [`sinnix://gateway/v2/actions/jobs.query`](sinnix://gateway/v2/actions/jobs.query)                 |

Direct-owner fallback semantics: `bd 1.1.0-dev` uses the canonical standalone Dolt workspace resolved through the canonical worktree and `.beads/redirect`; Dolt remains authoritative, JSONL is an optional export, and snapshot publication is explicit through `beads.operate` with `snapshot.publish`.

<!-- END GENERATED GATEWAY V2 REFERENCE -->
