# Agent gateway

The Sinnix agent gateway is one official-SDK MCP server with three explicit authority principals. Every gateway action is one MCP tool whose input and output schemas are generated from its pydantic models, so the contract a client sees in `tools/list` is the contract the handler validates. It reads canonical project and runtime evidence, queues jobs through agentctl in process, and keeps transport outside the MCP process.

## Architecture

```text
ChatGPT operator connector
    -> OpenAI Secure MCP Tunnel
    -> tunnel-client user service
    -> stdio: sinnix-agent-gateway-operator-mcp
    -> typed actions over the project, job, artifact, audit and observe services

Local coordinators
    -> sinnix-agent-control-mcp
    -> stdio: sinnix-agent-gateway --principal agent-control
    -> agentctl's launch routes, in process
    -> a pueue task, its log and typed result

ChatGPT observer connector
    -> separate OpenAI Secure MCP Tunnel
    -> stdio: sinnix-agent-gateway-observer-mcp
```

The gateway owns no HTTP server and no listening port. The official OpenAI tunnel owns the remote connection and launches the MCP server over stdio. The gateway retains principal and capability authorization, project authorization, envelopes, audit and redaction. Jobs are pueue tasks: agentctl (`docs/agentctl.md`) owns the launch input, the pool, the log, the typed result and cancellation; the gateway calls its routes in process and implements no second job controller.

## Principals

| Principal       | Intended caller                                    | Reads                                                            | Jobs                | Writes                                                       |
| --------------- | -------------------------------------------------- | ---------------------------------------------------------------- | ------------------- | ------------------------------------------------------------ |
| `observer`      | Read-only ChatGPT connector and local inspection   | Projects that opt into `observerRead`, machine, artifacts, audit | No                  | No                                                           |
| `agent-control` | Trusted local coordinators                         | Yes                                                              | Start, wait, cancel | No                                                           |
| `operator`      | Local testing and a write-capable remote workspace | Yes                                                              | Yes                 | Files, projects, Beads, desktop, terminals, browser, machine |

An action declares its principals; the tool manifest a principal receives contains only its actions, so an observer never sees `files.change` and cannot reach it by name. The runtime enforces the same capability again before any owner is called.

## Actions

Actions are declared once in `sinnix_agent_gateway/actions/` as an `Action` with an `Input` model, an `Output` model, a handler, a verb family, principals, aliases, affordances and examples. The family (`status`, `catalog`, `query`, `get`, `context`, `events`, `wait`, `change`, `operate`, `run`) drives the MCP annotations and the effect class: read families are audited reads; `change`, `operate` and `run` require an `idempotency_key`, accept `preconditions`, and replay a stored response for a repeated key.

Locators replace mandatory canonical refs as input: a host path, a project id, a bead id or title fragment, a window title, a kitty id, a page URL fragment or a unit name is accepted wherever a `sinnix://` ref is. Resolution returns exactly one ref, fails `not_found`, or fails `conflict` with the candidate refs; an effectful action never guesses. Every response carries the resolved canonical ref and, where useful, `affordances` naming the next actions.

Binary content never rides as text: `files.read`, `desktop.screenshot`, `browser.screenshot` and `artifacts.read` return images as MCP image content blocks and other binary as resource blocks, with the artifact's MIME, size and SHA-256 in the structured data.

`gateway.catalog` searches actions, resource kinds and brokered MCP tools by plain words (names, summaries, aliases, owners, resource kinds). `gateway.status` reports the principal, the live tool manifest hash, the Nix-approved hash, the connector-observed hash and per-route availability including each brokered MCP server.

The generated reference below lists every action; `docs/generated/agent-gateway-reference.md` carries the schemas and examples and `sinnix-agent-gateway catalog <action> --schema` prints them live.

## Interfaces

```bash
sinnix-agent-gateway-observer-mcp
sinnix-agent-control-mcp
sinnix-agent-gateway --principal operator call files.read --set path=/etc/os-release
sinnix-agent-gateway --principal operator call files.read --input '{"target":{"path":"/etc/os-release"}}'
sinnix-agent-gateway catalog files.patch --schema
sinnix-agent-gateway manifest
sinnix-agent-gateway approval-check
```

The CLI invokes the same action through the same runtime and principal; it validates the input against the action's model first and does not create an alternate route. Inputs larger than 262144 bytes are rejected.

Each endpoint's manifest command emits the canonical sorted tool manifest and its SHA-256; the selected principal's manifest is compared with its Nix-approved hash before startup. Because every tool carries its full schema, that one hash covers the whole action contract. The private state file `connector-snapshot.json` records an externally observed ChatGPT connector snapshot; `gateway.status` reports each comparison as `match`, `mismatch` or `unobserved` and never claims connector parity without an observation.

## Project and path authority

`sinnix.projects.entries` is the only project registry, filtered into each `/etc/sinnix/agent-gateway-<endpoint>.json` according to that endpoint's project scope. Project paths are always relative: reads and writes reject absolute paths, parent traversal, sensitive components and symlink escapes; tree traversal does not follow symlinks. Host-file actions take absolute paths and refuse secret roots for every principal but the operator. `projects.change` requires the checkout `head` and `dirty_sha256` preconditions; `files.patch` and `files.change` accept `expected_sha256`.

## Jobs and artifacts

The job owner (`sinnix_agent_gateway/execution.py`) dispatches onto agentctl in process. A job's identity is its pueue task id; its state is pueue's phase, terminal flag and exit code. `operations.run` queues a declared operation on the main checkout or a worktree, `shell.run` queues one operator argv confined to the checkout, `agent.for_bead` starts a batch with that bead as its one worker; `jobs.list`, `jobs.get`, `jobs.logs`, `jobs.wait`, `jobs.cancel` and `jobs.retry` read and control them. Gateway-owned artifacts are scoped to their creating principal; `operator` may read all.

## Audit and observe

Audit events live in a private SQLite WAL ledger; every call, including reads, appends a receipt and persists an immutable result snapshot. `events.tail` is principal-scoped and binds every row to `sinnix://receipts/{receipt_id}`; `audit.verify` checks the chain. `machine.snapshot` and `machine.query` delegate to `sinnix-observe`; `machine.operate` sends one typed request to the ops reducer with the revision it returned.

## NixOS configuration

```nix
sinnix.services.agent-gateway.enable = true;
sinnix.services.agent-gateway.endpoints.operator = {
  enable = true;
  principal = "operator";
  tunnelId = "tunnel_...";
  runtimeKeyFile = "/run/agenix/openai-tunnel-runtime-key";
  approvedManifestHash = "...";
};
```

Every enabled endpoint receives its own generated config, MCP wrapper, approval gate, state directory, runtime credential, health port, systemd user service and runtime surface. Prime enables the private operator endpoint on loopback port 3088.

## Deployment and proof

1. Provision the endpoint's tunnel ID and dedicated runtime credential.
2. Run `switch` so the pinned SDK, tunnel client, endpoint configs, runtime inventory and user units are one generation.
3. Compare the endpoint's `manifest` output with a direct stdio `tools/list`; `approval-check` must pass.
4. Verify `/healthz` and `/readyz` on the configured loopback health port.
5. Refresh the ChatGPT connector, approve its tool snapshot, and run `gateway.status`, `gateway.catalog` and one `files.read` of an image; record the observed manifest hash in `connector-snapshot.json`.

<!-- BEGIN GENERATED GATEWAY V2 REFERENCE -->

## Generated reference

This section is generated from the action set. Revision `v3-typed-actions`, catalog SHA-256 `23ea3f1e63bf903ef81fcbbace343a31149631e79960da38391e8c396ab32af1`.

The full schemas and examples are in [the generated gateway reference](generated/agent-gateway-reference.md). The matching agent skill is [agent-gateway](../dots/_ai/skills/agent-gateway/SKILL.md).

| Action                  | Family    | Owner              | Principals                          | Summary                                                                                                                                                                                                            |
| ----------------------- | --------- | ------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `gateway.status`        | `status`  | `gateway`          | `agent-control, observer, operator` | Report the principal, contract hashes, tool count and per-route availability.                                                                                                                                      |
| `gateway.catalog`       | `catalog` | `gateway`          | `agent-control, observer, operator` | Every action is also an MCP tool with its full schema in tools/list; the catalog adds aliases, affordances, resource kinds and the brokered MCP tool inventory (lynchpin, sinex, polylogue).                       |
| `files.stat`            | `query`   | `files`            | `observer, operator`                | Describe one host path: kind, size, mode, owner, timestamps, MIME, hash.                                                                                                                                           |
| `files.list`            | `query`   | `files`            | `observer, operator`                | List a directory with a canonical ref for every child.                                                                                                                                                             |
| `files.read`            | `query`   | `files`            | `observer, operator`                | Read a file: text inline, images as an image block, other binary as a resource block.                                                                                                                              |
| `files.search`          | `query`   | `files`            | `observer, operator`                | Without content_regex the search is over paths (fd); with it, matching lines are returned (ripgrep --json). Results are bounded by limit and timeout.                                                              |
| `files.patch`           | `change`  | `files`            | `operator`                          | Pass expected_sha256 from the prior read so a concurrent change is refused instead of overwritten. Unified hunks are applied individually; rejected hunks are reported.                                            |
| `files.change`          | `change`  | `files`            | `operator`                          | Copy and move never overwrite an existing destination. Remove supports regular files only.                                                                                                                         |
| `projects.list`         | `query`   | `projects`         | `agent-control, observer, operator` | List the projects this principal may read, with canonical refs.                                                                                                                                                    |
| `projects.get`          | `get`     | `projects`         | `agent-control, observer, operator` | The checkout row carries head and dirty_sha256, the preconditions projects.change requires.                                                                                                                        |
| `projects.tree`         | `query`   | `projects`         | `agent-control, observer, operator` | List files under a project-relative directory without following symlinks.                                                                                                                                          |
| `projects.read`         | `query`   | `projects`         | `agent-control, observer, operator` | Read a bounded line range of one project file.                                                                                                                                                                     |
| `projects.diff`         | `query`   | `projects`         | `agent-control, observer, operator` | Show uncommitted changes in a checkout, optionally against a git ref.                                                                                                                                              |
| `projects.search`       | `query`   | `projects`         | `agent-control, observer, operator` | Search project file contents with ripgrep.                                                                                                                                                                         |
| `projects.change`       | `change`  | `projects`         | `operator`                          | Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get.                                          |
| `projects.context`      | `context` | `projects`         | `agent-control, observer, operator` | Components are budgeted independently; an unavailable component names its reason and source ref so the caller can follow the direct route.                                                                         |
| `beads.query`           | `query`   | `beads`            | `agent-control, observer, operator` | limit is passed to the owner so at most limit rows per project are read; page.next_cursor continues the same snapshot.                                                                                             |
| `beads.get`             | `get`     | `beads`            | `agent-control, observer, operator` | Read one bead by ref, id or title fragment, with optional comments, history, dependencies or graph.                                                                                                                |
| `beads.change`          | `change`  | `beads`            | `operator`                          | expected.expected_task_revision/expected_etag come from beads.get. Use mode=preview to see the compiled command and a preview_digest before applying.                                                              |
| `beads.changeset`       | `change`  | `beads`            | `operator`                          | No global rollback: each applied step reports its outcome and a compensation hint. Preview first, then apply with the returned preview_digest.                                                                     |
| `beads.operate`         | `operate` | `beads`            | `operator`                          | Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.                                                                                                                |
| `jobs.list`             | `query`   | `systemd-jobs`     | `agent-control, observer, operator` | List queued jobs (pueue tasks) newest first, optionally for one project.                                                                                                                                           |
| `jobs.get`              | `get`     | `systemd-jobs`     | `agent-control, observer, operator` | One job's state and bead binding, with its log range or typed result on request.                                                                                                                                   |
| `jobs.logs`             | `get`     | `systemd-jobs`     | `agent-control, observer, operator` | A byte range of a job's bounded log (workload output, then the wrapper's stderr).                                                                                                                                  |
| `jobs.wait`             | `wait`    | `systemd-jobs`     | `agent-control, observer, operator` | The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job.                                                                                                                 |
| `jobs.cancel`           | `operate` | `systemd-jobs`     | `agent-control, operator`           | Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.                                                                                                          |
| `jobs.retry`            | `operate` | `systemd-jobs`     | `agent-control, operator`           | Re-run a terminal job in place with the same launch input and id (pueue restart).                                                                                                                                  |
| `operations.run`        | `run`     | `systemd-jobs`     | `agent-control, operator`           | Queue one project-declared operation in its declared pool on the root or a worktree.                                                                                                                               |
| `shell.run`             | `run`     | `systemd-jobs`     | `operator`                          | cwd is confined to the checkout; the job's log carries the output.                                                                                                                                                 |
| `agent.for_bead`        | `run`     | `systemd-jobs`     | `agent-control, operator`           | backend, model and effort default to the bead's model policy. Refused when a member is claimed or already in a run.                                                                                                |
| `wait.for`              | `wait`    | `waits`            | `agent-control, observer, operator` | Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token. |
| `events.tail`           | `events`  | `events`           | `agent-control, observer, operator` | Pass next_cursor back to continue; a cursor from another principal or project scope fails stale_cursor.                                                                                                            |
| `context.compose`       | `context` | `context`          | `agent-control, observer, operator` | Each component is budgeted and isolated: an unavailable owner marks its component unavailable with a reason instead of failing the call. The snapshot is persisted under snapshot_ref.                             |
| `desktop.snapshot`      | `status`  | `desktop`          | `observer, operator`                | One observation of the desktop: monitors, workspaces, focus, every window with geometry, and a generation stamp.                                                                                                   |
| `desktop.screenshot`    | `query`   | `desktop`          | `observer, operator`                | full captures the focused output through the HDR-aware screenshot owner; window/rect/monitor targets capture with grim. On HDR outputs a corrected SDR variant is produced and preferred for the image block.      |
| `desktop.tree`          | `query`   | `desktop`          | `observer, operator`                | Fails unavailable when the pyatspi bindings are absent from the gateway environment; Chromium apps expose a tree only when launched with accessibility forced on.                                                  |
| `desktop.operate`       | `operate` | `desktop`          | `operator`                          | Pointer clicks, drags and scrolls need a virtual pointer tool (ydotool) on the host and fail unavailable without one; cursor moves always work. Window targets are natural locators; ambiguity returns candidates. |
| `terminals.list`        | `catalog` | `terminals`        | `observer, operator`                | Every kitty window with its ref, title, cwd, shell pid, focus and foreground processes.                                                                                                                            |
| `terminals.get`         | `get`     | `terminals`        | `observer, operator`                | Resolve one terminal by ref, kitty id, title, cwd, pid or focus.                                                                                                                                                   |
| `terminals.screen`      | `query`   | `terminals`        | `observer, operator`                | The visible screen text of one terminal.                                                                                                                                                                           |
| `terminals.scrollback`  | `query`   | `terminals`        | `observer, operator`                | The last N lines of a terminal's history, screen, or last command output.                                                                                                                                          |
| `terminals.processes`   | `query`   | `terminals`        | `observer, operator`                | Foreground processes of one terminal and whether its shell is at a prompt.                                                                                                                                         |
| `terminals.send`        | `operate` | `terminals`        | `operator`                          | Send text (optionally with Enter or bracketed paste) or key presses to one terminal.                                                                                                                               |
| `terminals.run`         | `run`     | `terminals`        | `operator`                          | Completion and output rely on kitty shell integration (at_prompt, last_cmd_output). exit_status is reported only with capture_exit_status, which appends a visible marker to the command line.                     |
| `terminals.wait`        | `wait`    | `terminals`        | `observer, operator`                | Wait until a terminal is at its prompt, shows a regex, finishes a process, or changes title.                                                                                                                       |
| `terminals.focus`       | `operate` | `terminals`        | `operator`                          | Focus one kitty window.                                                                                                                                                                                            |
| `terminals.open`        | `operate` | `terminals`        | `operator`                          | Open a new kitty window (OS window, split or tab) with an optional cwd and command; returns its ref.                                                                                                               |
| `browser.pages`         | `catalog` | `browser`          | `observer, operator`                | List every open Chrome page with its ref; flags the gateway-owned pages that can be read, captured or operated.                                                                                                    |
| `browser.page`          | `get`     | `browser`          | `observer, operator`                | Element refs (g<generation>e<n>) are attached to the DOM for this snapshot; a later snapshot or reload replaces them, and a stale ref fails not_found.                                                             |
| `browser.screenshot`    | `query`   | `browser`          | `observer, operator`                | Screenshot a gateway-owned page through CDP; the image rides in an image block and is retained as an artifact.                                                                                                     |
| `browser.operate`       | `operate` | `browser`          | `operator`                          | Operator tabs are never accepted as targets, even when a locator matches one. Element targets take a snapshot ref or a CSS selector.                                                                               |
| `machine.snapshot`      | `status`  | `machine`          | `agent-control, observer, operator` | Each section carries its own availability and source; GPU and network report unavailable because no owner exposes them.                                                                                            |
| `machine.query`         | `query`   | `machine`          | `agent-control, observer, operator` | Read one sinnix-observe section with cursor paging, or the ops-reducer revision (operation=actions).                                                                                                               |
| `machine.units.list`    | `query`   | `machine`          | `agent-control, observer, operator` | List systemd units of one manager with load/active/sub state and a canonical ref each.                                                                                                                             |
| `machine.units.get`     | `get`     | `machine`          | `agent-control, observer, operator` | Describe one unit via systemctl show: states, main pid, cgroup, restarts, timestamps.                                                                                                                              |
| `machine.units.logs`    | `query`   | `machine`          | `agent-control, observer, operator` | Journal entries for one unit (journalctl -o json), bounded by line count and bytes.                                                                                                                                |
| `machine.operate`       | `operate` | `ops-reducer`      | `operator`                          | expected_revision must match machine.query operation=actions; the reducer receipt is verified against the submitted action and target.                                                                             |
| `machine.units.operate` | `operate` | `ops-reducer`      | `operator`                          | Start, stop or restart one unit through the ops reducer (reload and wait are not reducer actions).                                                                                                                 |
| `processes.list`        | `query`   | `machine`          | `agent-control, observer, operator` | List live processes filtered by name, pid, unit, cgroup or user, with a canonical ref each.                                                                                                                        |
| `processes.get`         | `get`     | `machine`          | `agent-control, observer, operator` | Describe one process: cmdline, cwd, exe, redacted env, cgroup/unit, parent, children, sockets, cpu and memory.                                                                                                     |
| `processes.tree`        | `query`   | `machine`          | `agent-control, observer, operator` | Parent/child process tree from one root or from every top-level process, bounded by depth and node count.                                                                                                          |
| `processes.signal`      | `operate` | `machine`          | `operator`                          | The reducer path is the attested one and needs expected_revision; the direct path is receipted by the gateway audit chain only.                                                                                    |
| `processes.wait`        | `wait`    | `machine`          | `agent-control, observer, operator` | Wait until a process (same pid and start ticks) exits, or the bounded timeout elapses.                                                                                                                             |
| `mcp.servers`           | `status`  | `mcp-broker`       | `observer, operator`                | Each probe runs initialize + tools/list with a 5 s bound; a timeout stores the upstream stderr as an artifact and returns its ref.                                                                                 |
| `mcp.tools`             | `catalog` | `mcp-broker`       | `observer, operator`                | Catalog of every admitted upstream tool with its namespaced ref, input schema and read/change effect.                                                                                                              |
| `mcp.call`              | `query`   | `mcp-broker`       | `observer, operator`                | Tools without a read-only annotation are refused here; use mcp.change (operator only).                                                                                                                             |
| `mcp.change`            | `change`  | `mcp-broker`       | `operator`                          | Invoke one upstream tool that is not declared read-only.                                                                                                                                                           |
| `artifacts.list`        | `catalog` | `artifacts`        | `agent-control, observer, operator` | List principal-visible artifacts with kind, owner, size and canonical ref.                                                                                                                                         |
| `artifacts.get`         | `get`     | `artifacts`        | `agent-control, observer, operator` | Metadata of one artifact without its bytes.                                                                                                                                                                        |
| `artifacts.read`        | `query`   | `artifacts`        | `agent-control, observer, operator` | Read an artifact: text inline with offsets, images as an image block, other binary as a resource block.                                                                                                            |
| `captures.query`        | `query`   | `captures`         | `agent-control, observer, operator` | List runtime-declared capture lanes, describe one, or read per-lane record deltas since a time.                                                                                                                    |
| `activity.query`        | `query`   | `captures`         | `agent-control, observer, operator` | Reads sinnix-capture-v1 envelope files under each lane path within the time window; coverage lists which lanes contributed and which have no envelope files.                                                       |
| `sessions.query`        | `query`   | `sessions`         | `observer, operator`                | List, read or search local coding-session JSONL files per provider.                                                                                                                                                |
| `memory.query`          | `query`   | `memory`           | `observer, operator`                | Search session-derived memory across providers or fetch one object by reference, with source provenance.                                                                                                           |
| `timeline.query`        | `query`   | `timeline`         | `observer, operator`                | Session evidence ordered by file mtime within an RFC 3339 window, per provider, without claiming unavailable upstreams.                                                                                            |
| `audit.verify`          | `status`  | `audit`            | `agent-control, observer, operator` | Verify the tamper-evident audit hash chain end to end.                                                                                                                                                             |
| `audit.receipt`         | `get`     | `audit`            | `agent-control, observer, operator` | Read one principal-scoped audit receipt by ref or id.                                                                                                                                                              |
| `results.get`           | `get`     | `results`          | `agent-control, observer, operator` | Read one immutable stored response snapshot by ref or id.                                                                                                                                                          |
| `capabilities.query`    | `catalog` | `capability-index` | `agent-control, observer, operator` | Search the generated machine capability index or describe one capability exactly.                                                                                                                                  |

<!-- END GENERATED GATEWAY V2 REFERENCE -->
