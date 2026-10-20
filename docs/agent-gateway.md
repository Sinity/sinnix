# Agent gateway

The agent gateway is one MCP server (official Python SDK) that gives the
operator's ChatGPT typed access to this machine. Every action is one MCP tool;
its input and output schemas are generated from pydantic models, so the schema
a client sees in `tools/list` is the one the handler validates.

```text
ChatGPT operator connector
    -> OpenAI Secure MCP Tunnel
    -> tunnel-client          (sinnix-agent-gateway.service)
    -> Streamable HTTP on a private Unix socket
                              (sinnix-agent-gateway-mcp.service)
    -> typed actions over projects, jobs, artifacts, audit and observation
```

The tunnel unit owns the remote connection; the MCP unit serves `/mcp` on a
socket in the user runtime directory. Jobs are pueue tasks owned by agentctl
(`docs/agentctl.md`); the gateway calls agentctl in process and is not a second
job controller. Local agents use the agentctl CLI directly.

## Authority

The gateway is single-user. It serves the operator's ChatGPT with the
operator's full power: reads, writes and jobs, with no read-only mode or
per-caller permissions. `actor` labels audit records; it does not select a
role. The configured project scope narrows repository discovery and project
actions, while host-file and shell tools retain their own action contracts.
Remote shells and jobs run in the operator's environment, including API keys
and tokens. Those values stay on the host: agentctl keeps them out of launch
inputs and masks them in logs, the gateway redacts them from audit rows and call
logs, job state is mode 0700, and launch inputs are excluded from backups.

Host-file actions take absolute paths. Project actions take relative paths and
reject absolute paths, parent traversal, sensitive components and symlink
escapes.

## Actions

Each action lives in `sinnix_agent_gateway/actions/` as an `Action`: input and
output models, a handler, a verb family, aliases, follow-up actions
and examples. List them with `gateway.catalog`, or print the full reference with
every schema and example:

```bash
sinnix-agent-gateway-generate --reference
sinnix-agent-gateway catalog <action> --schema     # one action, live
```

The family (`status`, `catalog`, `query`, `get`, `context`, `events`, `wait`,
`change`, `operate`, `run`) sets the MCP annotations and the effect class.

- **Reads** are audited and side-effect free.
- **Effects** (`change`, `operate`, `run`) require an `idempotency_key` and
  accept `preconditions`. A repeated key replays the confirmed response. A
  concurrent call with a pending key is refused. An interrupted call becomes
  `indeterminate` and is never retried automatically.
- **Lost responses:** when a reply is lost (a tunnel 502 or deadline),
  `audit.operation` with the action and key reports `confirmed` (with the
  committed response), `pending`, `indeterminate` or `unknown`, without running
  anything.
- **Reconciliation:** `operations.run` and `shell.run` reconcile interrupted
  calls through agentctl launch identities. Machine actions and process stop
  reconcile only exact confirmed owner receipts.
- **Preconditions** are best-effort checks unless the owner guarantees an
  atomic compare-and-write (Beads `expected_version`, file `expected_sha256`).

**Locators.** Wherever a `sinnix://` ref is accepted, a host path, project id,
bead id or title fragment, window title, kitty id, page URL fragment or unit
name also works. Resolution yields exactly one ref, `not_found`, or `conflict`
with the candidates; an effectful action never guesses. A ref is also an MCP
resource: `resources/read` returns what the owning action returns.

**Binary content.** `files.read`, `desktop.screenshot`, `browser.screenshot`
and `artifacts.read` return images as MCP image blocks and other binary,
including PDFs, as resource blocks, with MIME type, size and SHA-256.

**Results and artifacts.** Every call stores its full result as an immutable
observation, readable later through `results.get`. A response too large for the
client budget (`maxResultBytes`) returns an artifact ref instead of truncating;
`artifacts.read` pages it by `offset`/`next_offset`.

**Discovery.** `gateway.catalog` searches actions, resource kinds and brokered
MCP tools by plain words. `gateway.describe` returns one action's schemas and
policy. `gateway.read`, `gateway.change` and `gateway.run` invoke an exact
action by name when a client has not loaded its typed tool. `gateway.status`
reports the live and package-generated manifest hashes, the last
recorded connector hash, and per-route availability.

**Components.** Composite answers (`context.compose`, `projects.context`)
report each part's own status: `available`, `degraded` (answered with named
gaps in `component_failures`), `empty` or `unavailable`. The whole answer takes
the worst part's status.

## CLI

```bash
sinnix-agent-gateway call files.read \
  --input '{"target":{"path":"/etc/os-release"}}'
sinnix-agent-gateway call files.read \
  --set target='{"path":"/etc/os-release"}'
sinnix-agent-gateway catalog files.patch --schema
sinnix-agent-gateway manifest
sinnix-agent-gateway manifest-check
```

The CLI runs the same action through the same runtime. `--set KEY=VALUE`
parses VALUE as JSON when it is JSON. `--input-file` and `--stdin` read one JSON
object; for large file bodies, write an artifact and pass it as a `source`.

## Projects

Projects come from `sinnix.projects.entries` and the private runtime catalog,
then `sinnix.services.agent-gateway.projects`, when set, narrows them. A configured path names a
Git repository; a discovered checkout must share its common directory. For a
bare repository, set `defaultCheckout` to give project-level reads a default;
otherwise reads name a checkout id from `projects.list`.

- `projects.change` writes inline `content`, a `patch`, or a `source` artifact,
  and needs at least one checkout or file-content precondition.
- `projects.read` and `projects.read_many` check that the checkout revision is
  unchanged before and after reading.
- `projects.search` streams ripgrep matches; its cursor reads the same retained
  matches after later edits.
- `projects.export` streams tracked and non-ignored files to a ZIP artifact,
  excluding sensitive paths. Page with `start_after`, passing the page's
  `checkout_revision` as `expected_revision`.

## Jobs and batches

`operations.run` queues a declared project operation; `shell.run` queues one
argv confined to a checkout. `jobs.list`, `jobs.get`, `jobs.logs`, `jobs.wait`,
`jobs.queues`, `jobs.cancel`, `jobs.retry` and `jobs.clean` read and control any
job. A job has a numeric `task_id` (pueue's queue position) and a stable string `job_id`
that survives queue reordering; each
retry is a separate attempt with its own logs and result. `batches.*` wrap
agentctl batches (`batches.start`, `status`, `list`, `resume`, `land`).

`shell.run` picks a pool: `shell-quick` (width 8) for reads and short commands,
or `shell-long` (width 4) for agent CLIs (`claude`, `codex`, `gemini`,
`opencode`, `pi`, `cursor-agent`, `agentctl-agent`). `pool=auto`, the default,
detects them past `env`, `nohup`, `timeout` and `sh -c`. A quick-pool command
still running after 20 s stops counting against the width, so long work never
blocks the quick pool. `timeout_seconds` is an optional kill ceiling.

With `wait=true`, `shell.run` waits up to `wait_timeout_seconds` (default 5,
at most 30). It returns `outcome` (`terminal`, `running` or `queued`). The two
non-terminal outcomes carry a continuation and a `queue` view: the pool width,
running jobs with age, and this job's position. `jobs.wait` with `output_offset`
returns only new log bytes.

## Beads, sessions and evidence

- **Beads** actions use the typed contracts of the packaged `bd owner` command.
  `beads.read` exposes beads queries and paging; `beads.query` pages through a
  pinned revision and stores the pages as an immutable result. `beads.create`,
  `beads.update`, `beads.close` and `beads.dependencies.add` are the specific
  writes. `beads.changeset` applies one project's ordered batch atomically.
  Row versions are 64-bit, so they travel as decimal strings; `expected_version`
  accepts them back unchanged.
- **Provenance.** Write `split_from` or `residual_of` as metadata on the new
  task (`bd update <id> --set-metadata 'split_from=<ref>'`).
  `discovered-from` and `supersedes` are native dependency edges.
- **Sessions.** `sessions.*`, `timeline.query` and `memory.raw.search`
  delegate to Polylogue.
- **Context and progress.** `context.compose`, `projects.context` and
  `campaign.progress` delegate to Lynchpin.
- **Machine.** `machine.snapshot` and `machine.query` delegate to
  `sinnix-observe`. `machine.prepare` and `machine.operate` send typed requests
  to the hub server.

The checked-in Beads, Polylogue and Lynchpin input models are generated from the
owners' published contracts (`generate_beads_inputs.py`,
`generate_owner_inputs.py`); package checks compare them with the pinned
sources.

## Audit and events

Every call, including reads, appends a receipt to a private SQLite ledger and
stores its result. `audit.verify` checks the receipt chain. `events.tail` merges
audit receipts, Git revisions, Beads revisions, job state and runtime
transitions, rotating between sources so a busy one cannot starve the rest.

Each remote call also writes one `gateway.call` JSON line to the MCP unit's
journal: action, outcome, redacted arguments, timings and the receipt id. Its
`request_id` matches the tunnel's `cmd_request_id`.

## Remote deadline

OpenAI's control plane drops a tunnelled response after about 120 s. To stay
inside that:

- Handlers run blocking work in worker threads; the tunnel client dispatches up
  to 32 calls at once.
- A remote read still running at 100 s returns a typed `deadline` error.
- Waits (`jobs.wait`, `wait.for`, `processes.wait`, `terminals.wait`) cap a
  remote `timeout_seconds` at 90 and return a continuation.
- Long work runs as a job and returns its handle.

## Brokered MCP tools

The gateway brokers the MCP servers in `flake/data/mcp-registry.nix`. A brokered
call counts as a read only if the owner annotates the tool read-only, or the
registry lists it in `gatewayReadOnlyTools` or `gatewayReadOnlyRoutes`. A route
names one tool plus argument values that must all match. Reads go through
`mcp.call`; everything else needs `mcp.change`. The last complete tool list is
cached for discovery, but every call checks the live server and current policy.

## Filesystem moves

Same-filesystem moves use one `renameat2(RENAME_NOREPLACE)`: never a link and
unlink, and never an overwrite. Cross-filesystem moves copy, verify, then remove
the source. If removal fails, both paths remain and the receipt says so. A batch
returns a partial receipt; there is no batch rollback.

## Configuration and deployment

```nix
sinnix.services.agent-gateway = {
  enable = true;
  tunnelId = "tunnel_...";
  # runtimeKeyFile defaults to /run/agenix/openai-tunnel-runtime-key.
};
```

**Units.** The gateway runs a tunnel unit and an MCP unit, keeps its state in
`~/.local/state/sinnix/agent-gateway/operator`, and serves tunnel health on port 3088. The tunnel client also starts a
`codex app-server`, so ChatGPT can reach the local Codex.

- **MCP unit:** runs in `agenttool.slice` with `MemoryHigh=4G` and
  `MemoryMax=6G`. On SIGTERM it drains for 5 s and exits by 8 s.
- **Restarts:** activation restarts the tunnel only when its own inputs change.
  Gateway code changes restart only the MCP unit, and the tunnel reconnects.

**Manifest check.** At startup the MCP unit compares its live tool schemas with
the package-generated manifest. `manifest-check` runs the same comparison.

**Deploying.** After provisioning the tunnel id and runtime key:

1. `switch`.
2. Check `/healthz` and `/readyz` on the health port.
3. Refresh the ChatGPT connector, then inspect the schema it actually exposes.
   For example, `jobs.wait` takes a target with numeric `task_id` and optional
   string `job_id`. If the client still requires numeric `job_id`, its cached
   schema is stale; refresh or reconnect that client before using job controls.
4. Run `gateway.status` and compare the live and package manifest hashes.
   Record the client-observed hash in `connector-snapshot.json` only after
   checking the client contract. The snapshot is historical evidence;
   `current_model_visibility=unknown` means the gateway cannot inspect the
   client's loaded tools. A local manifest check cannot verify a remote refresh.

To stop per-call approval prompts, enable the app's **Allow all actions**
permission in ChatGPT settings. That setting is client-side and changes nothing
in the gateway's own checks.
