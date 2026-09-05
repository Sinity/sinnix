---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway actions through their typed MCP tools or the sinnix-agent-gateway CLI.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v3-typed-actions -->
<!-- gateway-catalog-sha256: 23ea3f1e63bf903ef81fcbbace343a31149631e79960da38391e8c396ab32af1 -->

# Agent Gateway

Every gateway action is one MCP tool named after the action; its input schema in `tools/list` is the contract and its output envelope schema is the `sinnix://gateway/v2/actions/<name>` resource. Paths, ids, titles and unit names are accepted where a canonical `sinnix://` ref is; responses return the canonical ref and `affordances` naming the next actions. Images arrive as image content blocks, other binary as resource blocks.

## Invocation

- MCP: call the tool by action name with the fields of its input schema.
- CLI: `sinnix-agent-gateway call <action> --input '{...}'` or `--set key=value` (values parse as JSON); `--principal` selects authority. `sinnix-agent-gateway catalog <action> --schema` prints the live schemas, `--example` the examples, `catalog --complete <prefix>` lists names.
- Discovery: `gateway.catalog` with a plain-words `query` finds actions, resources and brokered MCP tools; `gateway.status` reports contract hashes and route availability.

Effectful actions (families change, operate, run) require `idempotency_key`; replaying the same key with the same request returns the stored response. Preconditions such as `expected_sha256` or checkout `head` fail with `precondition_failed` instead of overwriting.

## Actions

### status

- `gateway.status` — Report the principal, contract hashes, tool count and per-route availability.
- `desktop.snapshot` — One observation of the desktop: monitors, workspaces, focus, every window with geometry, and a generation stamp.
- `machine.snapshot` — Each section carries its own availability and source; GPU and network report unavailable because no owner exposes them.
- `mcp.servers` — Each probe runs initialize + tools/list with a 5 s bound; a timeout stores the upstream stderr as an artifact and returns its ref.
- `audit.verify` — Verify the tamper-evident audit hash chain end to end.

### catalog

- `gateway.catalog` — Every action is also an MCP tool with its full schema in tools/list; the catalog adds aliases, affordances, resource kinds and the brokered MCP tool inventory (lynchpin, sinex, polylogue).
- `terminals.list` — Every kitty window with its ref, title, cwd, shell pid, focus and foreground processes.
- `browser.pages` — List every open Chrome page with its ref; flags the gateway-owned pages that can be read, captured or operated.
- `mcp.tools` — Catalog of every admitted upstream tool with its namespaced ref, input schema and read/change effect.
- `artifacts.list` — List principal-visible artifacts with kind, owner, size and canonical ref.
- `capabilities.query` — Search the generated machine capability index or describe one capability exactly.

### query

- `files.stat` — Describe one host path: kind, size, mode, owner, timestamps, MIME, hash.
- `files.list` — List a directory with a canonical ref for every child.
- `files.read` — Read a file: text inline, images as an image block, other binary as a resource block.
- `files.search` — Without content_regex the search is over paths (fd); with it, matching lines are returned (ripgrep --json). Results are bounded by limit and timeout.
- `projects.list` — List the projects this principal may read, with canonical refs.
- `projects.tree` — List files under a project-relative directory without following symlinks.
- `projects.read` — Read a bounded line range of one project file.
- `projects.diff` — Show uncommitted changes in a checkout, optionally against a git ref.
- `projects.search` — Search project file contents with ripgrep.
- `beads.query` — limit is passed to the owner so at most limit rows per project are read; page.next_cursor continues the same snapshot.
- `jobs.list` — List queued jobs (pueue tasks) newest first, optionally for one project.
- `desktop.screenshot` — full captures the focused output through the HDR-aware screenshot owner; window/rect/monitor targets capture with grim. On HDR outputs a corrected SDR variant is produced and preferred for the image block.
- `desktop.tree` — Fails unavailable when the pyatspi bindings are absent from the gateway environment; Chromium apps expose a tree only when launched with accessibility forced on.
- `terminals.screen` — The visible screen text of one terminal.
- `terminals.scrollback` — The last N lines of a terminal's history, screen, or last command output.
- `terminals.processes` — Foreground processes of one terminal and whether its shell is at a prompt.
- `browser.screenshot` — Screenshot a gateway-owned page through CDP; the image rides in an image block and is retained as an artifact.
- `machine.query` — Read one sinnix-observe section with cursor paging, or the ops-reducer revision (operation=actions).
- `machine.units.list` — List systemd units of one manager with load/active/sub state and a canonical ref each.
- `machine.units.logs` — Journal entries for one unit (journalctl -o json), bounded by line count and bytes.
- `processes.list` — List live processes filtered by name, pid, unit, cgroup or user, with a canonical ref each.
- `processes.tree` — Parent/child process tree from one root or from every top-level process, bounded by depth and node count.
- `mcp.call` — Tools without a read-only annotation are refused here; use mcp.change (operator only).
- `artifacts.read` — Read an artifact: text inline with offsets, images as an image block, other binary as a resource block.
- `captures.query` — List runtime-declared capture lanes, describe one, or read per-lane record deltas since a time.
- `activity.query` — Reads sinnix-capture-v1 envelope files under each lane path within the time window; coverage lists which lanes contributed and which have no envelope files.
- `sessions.query` — List, read or search local coding-session JSONL files per provider.
- `memory.query` — Search session-derived memory across providers or fetch one object by reference, with source provenance.
- `timeline.query` — Session evidence ordered by file mtime within an RFC 3339 window, per provider, without claiming unavailable upstreams.

### get

- `projects.get` — The checkout row carries head and dirty_sha256, the preconditions projects.change requires.
- `beads.get` — Read one bead by ref, id or title fragment, with optional comments, history, dependencies or graph.
- `jobs.get` — One job's state and bead binding, with its log range or typed result on request.
- `jobs.logs` — A byte range of a job's bounded log (workload output, then the wrapper's stderr).
- `terminals.get` — Resolve one terminal by ref, kitty id, title, cwd, pid or focus.
- `browser.page` — Element refs (g<generation>e<n>) are attached to the DOM for this snapshot; a later snapshot or reload replaces them, and a stale ref fails not_found.
- `machine.units.get` — Describe one unit via systemctl show: states, main pid, cgroup, restarts, timestamps.
- `processes.get` — Describe one process: cmdline, cwd, exe, redacted env, cgroup/unit, parent, children, sockets, cpu and memory.
- `artifacts.get` — Metadata of one artifact without its bytes.
- `audit.receipt` — Read one principal-scoped audit receipt by ref or id.
- `results.get` — Read one immutable stored response snapshot by ref or id.

### context

- `projects.context` — Components are budgeted independently; an unavailable component names its reason and source ref so the caller can follow the direct route.
- `context.compose` — Each component is budgeted and isolated: an unavailable owner marks its component unavailable with a reason instead of failing the call. The snapshot is persisted under snapshot_ref.

### events

- `events.tail` — Pass next_cursor back to continue; a cursor from another principal or project scope fails stale_cursor.

### wait

- `jobs.wait` — The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job.
- `wait.for` — Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token.
- `terminals.wait` — Wait until a terminal is at its prompt, shows a regex, finishes a process, or changes title.
- `processes.wait` — Wait until a process (same pid and start ticks) exits, or the bounded timeout elapses.

### change

- `files.patch` — Pass expected_sha256 from the prior read so a concurrent change is refused instead of overwritten. Unified hunks are applied individually; rejected hunks are reported.
- `files.change` — Copy and move never overwrite an existing destination. Remove supports regular files only.
- `projects.change` — Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get.
- `beads.change` — expected.expected_task_revision/expected_etag come from beads.get. Use mode=preview to see the compiled command and a preview_digest before applying.
- `beads.changeset` — No global rollback: each applied step reports its outcome and a compensation hint. Preview first, then apply with the returned preview_digest.
- `mcp.change` — Invoke one upstream tool that is not declared read-only.

### operate

- `beads.operate` — Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.
- `jobs.cancel` — Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.
- `jobs.retry` — Re-run a terminal job in place with the same launch input and id (pueue restart).
- `desktop.operate` — Pointer clicks, drags and scrolls need a virtual pointer tool (ydotool) on the host and fail unavailable without one; cursor moves always work. Window targets are natural locators; ambiguity returns candidates.
- `terminals.send` — Send text (optionally with Enter or bracketed paste) or key presses to one terminal.
- `terminals.focus` — Focus one kitty window.
- `terminals.open` — Open a new kitty window (OS window, split or tab) with an optional cwd and command; returns its ref.
- `browser.operate` — Operator tabs are never accepted as targets, even when a locator matches one. Element targets take a snapshot ref or a CSS selector.
- `machine.operate` — expected_revision must match machine.query operation=actions; the reducer receipt is verified against the submitted action and target.
- `machine.units.operate` — Start, stop or restart one unit through the ops reducer (reload and wait are not reducer actions).
- `processes.signal` — The reducer path is the attested one and needs expected_revision; the direct path is receipted by the gateway audit chain only.

### run

- `operations.run` — Queue one project-declared operation in its declared pool on the root or a worktree.
- `shell.run` — cwd is confined to the checkout; the job's log carries the output.
- `agent.for_bead` — backend, model and effort default to the bead's model policy. Refused when a member is claimed or already in a run.
- `terminals.run` — Completion and output rely on kitty shell integration (at_prompt, last_cmd_output). exit_status is reported only with capture_exit_status, which appends a visible marker to the command line.

The complete schemas and examples are in `docs/generated/agent-gateway-reference.md`.

Catalog revision: `v3-typed-actions`. Catalog SHA-256: `23ea3f1e63bf903ef81fcbbace343a31149631e79960da38391e8c396ab32af1`.
