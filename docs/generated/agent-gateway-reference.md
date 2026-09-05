<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v3-typed-actions -->
<!-- gateway-catalog-sha256: 23ea3f1e63bf903ef81fcbbace343a31149631e79960da38391e8c396ab32af1 -->
# Sinnix Agent Gateway reference

Generated from `sinnix_agent_gateway.actions`. Every action is one MCP tool whose `tools/list` input schema is the one below; the catalog hash changes when an action, schema, principal set, example or affordance changes.

Revision: `v3-typed-actions`. Catalog SHA-256: `23ea3f1e63bf903ef81fcbbace343a31149631e79960da38391e8c396ab32af1`.

## Invocation

MCP: call the tool named after the action. CLI: `sinnix-agent-gateway call <action> --input '<json>'` or `--set key=value`; `sinnix-agent-gateway catalog <action> --schema` prints the live schemas.

## Resources

| Resource            | Owner              | Canonical reference                                      | Actions                                                                                                                                                                                                                                                                                            |
| ------------------- | ------------------ | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project`           | `projects`         | `sinnix://projects/{project_id}`                         | `agent.for_bead`, `beads.change`, `beads.changeset`, `beads.operate`, `beads.query`, `context.compose`, `events.tail`, `operations.run`, `projects.change`, `projects.context`, `projects.diff`, `projects.get`, `projects.list`, `projects.read`, `projects.search`, `projects.tree`, `shell.run` |
| `checkout`          | `projects`         | `sinnix://projects/{project_id}/checkouts/{checkout_id}` | `context.compose`, `operations.run`, `projects.change`, `projects.diff`, `projects.get`, `projects.read`, `projects.search`, `projects.tree`, `shell.run`                                                                                                                                          |
| `bead`              | `beads`            | `sinnix://projects/{project_id}/beads/{bead_id}`         | `agent.for_bead`, `beads.change`, `beads.changeset`, `beads.get`, `beads.query`, `wait.for`                                                                                                                                                                                                        |
| `task_authority`    | `beads`            | `sinnix://projects/{project_id}/task-authority`          | `beads.change`, `beads.changeset`, `beads.operate`, `beads.query`                                                                                                                                                                                                                                  |
| `job`               | `jobs`             | `sinnix://jobs/{job_id}`                                 | `agent.for_bead`, `context.compose`, `events.tail`, `jobs.cancel`, `jobs.get`, `jobs.list`, `jobs.logs`, `jobs.retry`, `jobs.wait`, `machine.operate`, `operations.run`, `shell.run`, `wait.for`                                                                                                   |
| `artifact`          | `artifacts`        | `sinnix://artifacts/{artifact_id}`                       | `artifacts.get`, `artifacts.list`, `artifacts.read`, `browser.screenshot`, `desktop.screenshot`                                                                                                                                                                                                    |
| `receipt`           | `audit`            | `sinnix://receipts/{receipt_id}`                         | `audit.receipt`, `audit.verify`, `events.tail`, `wait.for`                                                                                                                                                                                                                                         |
| `result`            | `results`          | `sinnix://results/{result_id}`                           | `results.get`                                                                                                                                                                                                                                                                                      |
| `machine_unit`      | `machine`          | `sinnix://machine/units/{manager}/{unit}`                | `machine.operate`, `machine.query`, `machine.snapshot`, `machine.units.get`, `machine.units.list`, `machine.units.logs`, `machine.units.operate`, `wait.for`                                                                                                                                       |
| `browser_page`      | `browser`          | `sinnix://browser/pages/{page_id}`                       | `browser.operate`, `browser.page`, `browser.pages`, `browser.screenshot`                                                                                                                                                                                                                           |
| `browser_workspace` | `browser`          | `sinnix://browser/agent-workspace`                       | `browser.operate`, `browser.pages`                                                                                                                                                                                                                                                                 |
| `process`           | `machine`          | `sinnix://processes/{pid}/{start_ticks}`                 | `machine.operate`, `machine.query`, `processes.get`, `processes.list`, `processes.signal`, `processes.tree`, `processes.wait`                                                                                                                                                                      |
| `terminal`          | `terminals`        | `sinnix://terminals/{terminal_id}`                       | `terminals.focus`, `terminals.get`, `terminals.list`, `terminals.open`, `terminals.processes`, `terminals.run`, `terminals.screen`, `terminals.scrollback`, `terminals.send`, `terminals.wait`, `wait.for`                                                                                         |
| `desktop`           | `desktop`          | `sinnix://desktop/current`                               | `desktop.operate`, `desktop.screenshot`, `desktop.snapshot`, `desktop.tree`                                                                                                                                                                                                                        |
| `host_file`         | `files`            | `sinnix://files/{file_token}`                            | `files.change`, `files.list`, `files.patch`, `files.read`, `files.search`, `files.stat`, `wait.for`                                                                                                                                                                                                |
| `mcp_tool`          | `mcp-broker`       | `sinnix://mcp/{server}/tools/{tool}`                     | `mcp.call`, `mcp.change`, `mcp.servers`, `mcp.tools`                                                                                                                                                                                                                                               |
| `capture_lane`      | `captures`         | `sinnix://captures/{lane}`                               | `activity.query`, `captures.query`, `wait.for`                                                                                                                                                                                                                                                     |
| `capability`        | `capability-index` | `sinnix://capabilities/{name}`                           | `capabilities.query`                                                                                                                                                                                                                                                                               |
| `session`           | `sessions`         | `sinnix://sessions/{provider}/{session_id}`              | `memory.query`, `sessions.query`, `timeline.query`                                                                                                                                                                                                                                                 |
| `context_snapshot`  | `context`          | `sinnix://contexts/{snapshot_id}`                        | `context.compose`                                                                                                                                                                                                                                                                                  |

## Actions

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
| `agent.for_bead`        | `run`     | `systemd-jobs`     | `agent-control, operator`           | backend, model and effort default to the bead's model policy. A bead that already has a worktree is refused with conflict.                                                                                         |
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

### `gateway.status`

Report the principal, contract hashes, tool count and per-route availability.

Family: `status`. Owner: `gateway`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: health, ready, capabilities, what can you do.

Follow-up actions: `gateway.catalog`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `GatewayStatus`; the full envelope schema is the `sinnix://gateway/v2/actions/gateway.status` resource and `sinnix-agent-gateway catalog gateway.status --schema`.

Examples:

Status:

```json
{}
```

### `gateway.catalog`

Every action is also an MCP tool with its full schema in tools/list; the catalog adds aliases, affordances, resource kinds and the brokered MCP tool inventory (lynchpin, sinex, polylogue).

Family: `catalog`. Owner: `gateway`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: search tools, discover, help, list actions, which tool.

Follow-up actions: `gateway.status`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "domain": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "family": {
      "anyOf": [
        {
          "enum": [
            "status",
            "catalog",
            "query",
            "get",
            "context",
            "events",
            "wait",
            "change",
            "operate",
            "run"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "include_mcp_tools": {
      "default": true,
      "description": "Also search brokered MCP server tools.",
      "type": "boolean"
    },
    "include_schemas": {
      "default": false,
      "description": "Attach each action's input schema (large).",
      "type": "boolean"
    },
    "limit": {
      "default": 50,
      "maximum": 500,
      "minimum": 1,
      "type": "integer"
    },
    "query": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Free text matched against names, summaries, aliases, owners and resource kinds."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "resource_kind": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Catalog`; the full envelope schema is the `sinnix://gateway/v2/actions/gateway.catalog` resource and `sinnix-agent-gateway catalog gateway.catalog --schema`.

Examples:

Screenshot capability:

```json
{
  "query": "screenshot"
}
```

Lynchpin tools:

```json
{
  "query": "lynchpin"
}
```

### `files.stat`

Describe one host path: kind, size, mode, owner, timestamps, MIME, hash.

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: file info, metadata, size, permissions.

Follow-up actions: `files.read`, `files.list`, `files.change`.

Input schema:

```json
{
  "$defs": {
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "follow_symlinks": {
      "default": true,
      "type": "boolean"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/FileLocator"
    },
    "with_sha256": {
      "default": true,
      "description": "Hash regular files; skipped above 256 MiB.",
      "type": "boolean"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `FileStat`; the full envelope schema is the `sinnix://gateway/v2/actions/files.stat` resource and `sinnix-agent-gateway catalog files.stat --schema`.

Examples:

Stat a file:

```json
{
  "target": {
    "path": "/etc/os-release"
  }
}
```

### `files.list`

List a directory with a canonical ref for every child.

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: ls, directory, folder, browse.

Follow-up actions: `files.stat`, `files.read`, `files.search`.

Input schema:

```json
{
  "$defs": {
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "descending": {
      "default": false,
      "type": "boolean"
    },
    "include_hidden": {
      "default": false,
      "type": "boolean"
    },
    "limit": {
      "default": 200,
      "maximum": 5000,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "sort": {
      "default": "name",
      "enum": [
        "name",
        "mtime",
        "size"
      ],
      "type": "string"
    },
    "target": {
      "$ref": "#/$defs/FileLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `DirectoryListing`; the full envelope schema is the `sinnix://gateway/v2/actions/files.list` resource and `sinnix-agent-gateway catalog files.list --schema`.

Examples:

List /realm/tmp:

```json
{
  "target": {
    "path": "/realm/tmp"
  }
}
```

### `files.read`

Read a file: text inline, images as an image block, other binary as a resource block.

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: cat, open, view, image, picture, screenshot file.

Follow-up actions: `files.patch`, `files.change`, `files.stat`.

Input schema:

```json
{
  "$defs": {
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "line_count": {
      "anyOf": [
        {
          "maximum": 10000,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "line_start": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "First line (1-based) for text reads."
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 4194304,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "description": "Byte offset for raw reads.",
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "representation": {
      "default": "auto",
      "description": "auto returns text inline for text types and a typed content block for binary types.",
      "enum": [
        "auto",
        "text",
        "binary"
      ],
      "type": "string"
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/FileLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `FileContent`; the full envelope schema is the `sinnix://gateway/v2/actions/files.read` resource and `sinnix-agent-gateway catalog files.read --schema`.

Examples:

Read /etc/os-release:

```json
{
  "target": {
    "path": "/etc/os-release"
  }
}
```

Lines 10-30 of a log:

```json
{
  "line_count": 21,
  "line_start": 10,
  "target": {
    "path": "/var/log/example.log"
  }
}
```

### `files.search`

Without content_regex the search is over paths (fd); with it, matching lines are returned (ripgrep --json). Results are bounded by limit and timeout.

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: find, grep, locate, rg, fd, search files, recent files.

Follow-up actions: `files.read`, `files.stat`, `files.list`.

Input schema:

```json
{
  "$defs": {
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "case_insensitive": {
      "default": false,
      "type": "boolean"
    },
    "content_regex": {
      "anyOf": [
        {
          "maxLength": 1024,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Search file contents; returns matching lines with context."
    },
    "context_lines": {
      "default": 0,
      "maximum": 5,
      "minimum": 0,
      "type": "integer"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "extensions": {
      "items": {
        "type": "string"
      },
      "maxItems": 32,
      "type": "array"
    },
    "fixed_string": {
      "default": false,
      "description": "Treat content_regex as a literal string.",
      "type": "boolean"
    },
    "include_hidden": {
      "default": false,
      "type": "boolean"
    },
    "kind": {
      "default": "any",
      "enum": [
        "any",
        "file",
        "directory",
        "symlink"
      ],
      "type": "string"
    },
    "limit": {
      "default": 100,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "max_bytes": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "max_depth": {
      "anyOf": [
        {
          "maximum": 64,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "min_bytes": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "modified_within_seconds": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "name_glob": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Glob on the file name, e.g. *.png"
    },
    "path_regex": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Regex on the full path."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "respect_ignore_files": {
      "default": true,
      "description": "Honour .gitignore and similar files.",
      "type": "boolean"
    },
    "roots": {
      "items": {
        "$ref": "#/$defs/FileLocator"
      },
      "maxItems": 8,
      "minItems": 1,
      "type": "array"
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 300,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "roots"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SearchResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.search` resource and `sinnix-agent-gateway catalog files.search --schema`.

Examples:

PNGs under /realm/tmp/work:

```json
{
  "extensions": [
    "png"
  ],
  "roots": [
    {
      "path": "/realm/tmp/work"
    }
  ]
}
```

Grep a string in a project:

```json
{
  "content_regex": "screenshot_probe",
  "context_lines": 1,
  "roots": [
    {
      "path": "/realm/project/sinnix"
    }
  ]
}
```

Files modified in the last two hours:

```json
{
  "modified_within_seconds": 7200,
  "roots": [
    {
      "path": "/realm/tmp"
    }
  ]
}
```

### `files.patch`

Pass expected_sha256 from the prior read so a concurrent change is refused instead of overwritten. Unified hunks are applied individually; rejected hunks are reported.

Family: `change`. Owner: `files`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: edit, apply diff, modify text, sed.

Follow-up actions: `files.read`, `files.stat`.

Input schema:

```json
{
  "$defs": {
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    },
    "RangeReplace": {
      "additionalProperties": false,
      "properties": {
        "end_line": {
          "description": "Last line to replace inclusive; start_line-1 inserts before start_line.",
          "minimum": 0,
          "type": "integer"
        },
        "expected_text": {
          "anyOf": [
            {
              "maxLength": 1048576,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "If given, the current lines in the range must equal this text."
        },
        "mode": {
          "const": "range",
          "default": "range",
          "type": "string"
        },
        "replacement": {
          "maxLength": 1048576,
          "type": "string"
        },
        "start_line": {
          "description": "First line to replace, 1-based.",
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "start_line",
        "end_line",
        "replacement"
      ],
      "type": "object"
    },
    "UnifiedPatch": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "const": "unified",
          "default": "unified",
          "type": "string"
        },
        "patch": {
          "description": "Unified diff hunks for this one file (--- / +++ headers optional).",
          "maxLength": 1048576,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "patch"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "dry_run": {
      "default": false,
      "description": "Validate without writing.",
      "type": "boolean"
    },
    "edit": {
      "discriminator": {
        "mapping": {
          "range": "#/$defs/RangeReplace",
          "unified": "#/$defs/UnifiedPatch"
        },
        "propertyName": "mode"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/UnifiedPatch"
        },
        {
          "$ref": "#/$defs/RangeReplace"
        }
      ]
    },
    "expected_sha256": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Hash from the prior read; the edit is refused if the file changed."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/FileLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "edit"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `PatchResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.patch` resource and `sinnix-agent-gateway catalog files.patch --schema`.

Examples:

Replace lines 3-4:

```json
{
  "edit": {
    "end_line": 4,
    "mode": "range",
    "replacement": "new line",
    "start_line": 3
  },
  "idempotency_key": "patch-notes-1",
  "target": {
    "path": "/realm/tmp/work/notes.md"
  }
}
```

Apply a unified diff:

```json
{
  "edit": {
    "mode": "unified",
    "patch": "@@ -1,1 +1,1 @@\n-old\n+new\n"
  },
  "expected_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "idempotency_key": "patch-notes-2",
  "target": {
    "path": "/realm/tmp/work/notes.md"
  }
}
```

### `files.change`

Copy and move never overwrite an existing destination. Remove supports regular files only.

Family: `change`. Owner: `files`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: write, save, rename, delete, mkdir, touch.

Follow-up actions: `files.stat`, `files.read`, `files.list`.

Input schema:

```json
{
  "$defs": {
    "AppendOp": {
      "additionalProperties": false,
      "properties": {
        "content": {
          "maxLength": 4194304,
          "type": "string"
        },
        "operation": {
          "const": "append",
          "default": "append",
          "type": "string"
        }
      },
      "required": [
        "content"
      ],
      "type": "object"
    },
    "CopyOp": {
      "additionalProperties": false,
      "properties": {
        "destination": {
          "$ref": "#/$defs/FileLocator"
        },
        "operation": {
          "const": "copy",
          "default": "copy",
          "type": "string"
        }
      },
      "required": [
        "destination"
      ],
      "type": "object"
    },
    "CreateOp": {
      "additionalProperties": false,
      "properties": {
        "content": {
          "default": "",
          "maxLength": 4194304,
          "type": "string"
        },
        "operation": {
          "const": "create",
          "default": "create",
          "type": "string"
        }
      },
      "type": "object"
    },
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    },
    "MkdirOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "mkdir",
          "default": "mkdir",
          "type": "string"
        },
        "parents": {
          "default": false,
          "type": "boolean"
        }
      },
      "type": "object"
    },
    "MoveOp": {
      "additionalProperties": false,
      "properties": {
        "destination": {
          "$ref": "#/$defs/FileLocator"
        },
        "operation": {
          "const": "move",
          "default": "move",
          "type": "string"
        }
      },
      "required": [
        "destination"
      ],
      "type": "object"
    },
    "RemoveOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "remove",
          "default": "remove",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ReplaceOp": {
      "additionalProperties": false,
      "properties": {
        "content": {
          "maxLength": 4194304,
          "type": "string"
        },
        "create": {
          "default": true,
          "description": "Create the file when absent.",
          "type": "boolean"
        },
        "operation": {
          "const": "replace",
          "default": "replace",
          "type": "string"
        }
      },
      "required": [
        "content"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "change": {
      "discriminator": {
        "mapping": {
          "append": "#/$defs/AppendOp",
          "copy": "#/$defs/CopyOp",
          "create": "#/$defs/CreateOp",
          "mkdir": "#/$defs/MkdirOp",
          "move": "#/$defs/MoveOp",
          "remove": "#/$defs/RemoveOp",
          "replace": "#/$defs/ReplaceOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/ReplaceOp"
        },
        {
          "$ref": "#/$defs/AppendOp"
        },
        {
          "$ref": "#/$defs/CreateOp"
        },
        {
          "$ref": "#/$defs/MkdirOp"
        },
        {
          "$ref": "#/$defs/CopyOp"
        },
        {
          "$ref": "#/$defs/MoveOp"
        },
        {
          "$ref": "#/$defs/RemoveOp"
        }
      ]
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected_sha256": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/FileLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "change"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ChangeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.change` resource and `sinnix-agent-gateway catalog files.change --schema`.

Examples:

Write a file:

```json
{
  "change": {
    "content": "hello\n",
    "operation": "replace"
  },
  "idempotency_key": "write-hello-1",
  "target": {
    "path": "/realm/tmp/work/hello.txt"
  }
}
```

Move a file:

```json
{
  "change": {
    "destination": {
      "path": "/realm/tmp/work/archive/hello.txt"
    },
    "operation": "move"
  },
  "idempotency_key": "move-hello-1",
  "target": {
    "path": "/realm/tmp/work/hello.txt"
  }
}
```

### `projects.list`

List the projects this principal may read, with canonical refs.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: repos, repositories, workspaces, which projects.

Follow-up actions: `projects.get`, `projects.context`, `beads.query`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProjectList`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.list` resource and `sinnix-agent-gateway catalog projects.list --schema`.

Examples:

List projects:

```json
{}
```

### `projects.get`

The checkout row carries head and dirty_sha256, the preconditions projects.change requires.

Family: `get`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: git status, branch, worktrees, checkouts, head, dirty.

Follow-up actions: `projects.tree`, `projects.diff`, `projects.change`, `projects.context`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "projection": {
      "default": "summary",
      "description": "summary: branch, change counts and latest commit plus the selected checkout; git: every checkout with head, branch and dirty_sha256; authority: summary, checkouts, code_revision and the Beads task authority.",
      "enum": [
        "summary",
        "git",
        "authority"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProjectView`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.get` resource and `sinnix-agent-gateway catalog projects.get --schema`.

Examples:

Summary by project id:

```json
{
  "target": {
    "project": "sinnix"
  }
}
```

All worktrees:

```json
{
  "projection": "git",
  "target": {
    "ref": "sinnix://projects/sinnix"
  }
}
```

Checkout containing a path:

```json
{
  "target": {
    "path": "/realm/project/sinnix/flake.nix"
  }
}
```

### `projects.tree`

List files under a project-relative directory without following symlinks.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: ls, file list, directory, layout.

Follow-up actions: `projects.read`, `projects.search`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_entries": {
      "default": 500,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "path": {
      "default": ".",
      "description": "Project-relative directory.",
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Tree`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.tree` resource and `sinnix-agent-gateway catalog projects.tree --schema`.

Examples:

Top-level modules:

```json
{
  "max_entries": 100,
  "path": "modules",
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.read`

Read a bounded line range of one project file.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: cat, open, view file, source.

Follow-up actions: `projects.change`, `projects.search`, `projects.diff`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "end_line": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 262144,
      "minimum": 1,
      "type": "integer"
    },
    "path": {
      "description": "Project-relative file path.",
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "start_line": {
      "default": 1,
      "minimum": 1,
      "type": "integer"
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target",
    "path"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProjectFile`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.read` resource and `sinnix-agent-gateway catalog projects.read --schema`.

Examples:

Read CLAUDE.md:

```json
{
  "end_line": 80,
  "path": "CLAUDE.md",
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.diff`

Show uncommitted changes in a checkout, optionally against a git ref.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: git diff, changes, what changed, working tree.

Follow-up actions: `projects.read`, `projects.get`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "git_ref": {
      "anyOf": [
        {
          "pattern": "^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Diff the worktree against this commit-ish; omitted diffs against the index."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Diff`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.diff` resource and `sinnix-agent-gateway catalog projects.diff --schema`.

Examples:

Working tree vs HEAD:

```json
{
  "git_ref": "HEAD",
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.search`

Search project file contents with ripgrep.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: grep, rg, find in files, where is.

Follow-up actions: `projects.read`, `projects.tree`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_matches": {
      "default": 200,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "query": {
      "description": "ripgrep regex.",
      "maxLength": 1000,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target",
    "query"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SearchResult`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.search` resource and `sinnix-agent-gateway catalog projects.search --schema`.

Examples:

Find a symbol:

```json
{
  "max_matches": 20,
  "query": "mkServiceModule",
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.change`

Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get.

Family: `change`. Owner: `projects`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: write file, edit, apply patch, save.

Follow-up actions: `projects.diff`, `projects.read`, `projects.get`.

Input schema:

```json
{
  "$defs": {
    "ApplyPatchOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "apply_patch",
          "default": "apply_patch",
          "type": "string"
        },
        "patch": {
          "description": "git-apply compatible patch.",
          "maxLength": 262144,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "patch"
      ],
      "type": "object"
    },
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    },
    "WriteOp": {
      "additionalProperties": false,
      "properties": {
        "content": {
          "maxLength": 262144,
          "type": "string"
        },
        "operation": {
          "const": "write",
          "default": "write",
          "type": "string"
        },
        "path": {
          "description": "Project-relative file path.",
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "path",
        "content"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "change": {
      "discriminator": {
        "mapping": {
          "apply_patch": "#/$defs/ApplyPatchOp",
          "write": "#/$defs/WriteOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/WriteOp"
        },
        {
          "$ref": "#/$defs/ApplyPatchOp"
        }
      ]
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected_dirty_sha256": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "dirty_sha256 from projects.get; at least one of expected_head or expected_dirty_sha256 is required."
    },
    "expected_head": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{40,64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "change"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ChangeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.change` resource and `sinnix-agent-gateway catalog projects.change --schema`.

Examples:

Write a file:

```json
{
  "change": {
    "content": "hello\n",
    "operation": "write",
    "path": "docs/notes.md"
  },
  "expected_head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "idempotency_key": "write-notes-1",
  "target": {
    "ref": "sinnix://projects/sinnix/checkouts/default"
  }
}
```

Apply a patch:

```json
{
  "change": {
    "operation": "apply_patch",
    "patch": "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
  },
  "expected_dirty_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "idempotency_key": "patch-readme-1",
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.context`

Components are budgeted independently; an unavailable component names its reason and source ref so the caller can follow the direct route.

Family: `context`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: orient, overview, where are we, triage, what is ready.

Follow-up actions: `projects.get`, `beads.query`, `projects.diff`, `projects.tree`.

Input schema:

```json
{
  "$defs": {
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "intent": {
      "default": "project.orientation",
      "enum": [
        "project.orientation",
        "project.triage"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ProjectLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProjectContext`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.context` resource and `sinnix-agent-gateway catalog projects.context --schema`.

Examples:

Orientation:

```json
{
  "target": {
    "project": "sinnix"
  }
}
```

Triage:

```json
{
  "intent": "project.triage",
  "target": {
    "project": "sinnix"
  }
}
```

### `beads.query`

limit is passed to the owner so at most limit rows per project are read; page.next_cursor continues the same snapshot.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: tasks, issues, todo, ready work, what is blocked, bd list, bd ready, backlog.

Follow-up actions: `beads.get`, `beads.change`, `projects.context`.

Input schema:

```json
{
  "$defs": {
    "GraphQuery": {
      "additionalProperties": false,
      "properties": {
        "bead": {
          "description": "Root bead id.",
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "depth": {
          "default": 1,
          "maximum": 20,
          "minimum": 1,
          "type": "integer"
        },
        "direction": {
          "default": "down",
          "enum": [
            "down",
            "up",
            "both"
          ],
          "type": "string"
        },
        "edge_type": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "max_rows": {
          "default": 200,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "mermaid": {
          "default": false,
          "type": "boolean"
        },
        "status": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "bead"
      ],
      "type": "object"
    },
    "MemoryQuery": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "anyOf": [
            {
              "maxLength": 256,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Recall one memory by key."
        },
        "query": {
          "anyOf": [
            {
              "maxLength": 1000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Search memories."
        }
      },
      "type": "object"
    },
    "NativeFilters": {
      "additionalProperties": false,
      "description": "Owner-native list filters; ready and stale_claims views accept a subset.",
      "properties": {
        "all": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "assignee": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "closed_after": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "closed_before": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "created_after": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "created_before": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "defer_after": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "defer_before": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "deferred": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "desc_contains": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "due_after": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "due_before": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "empty_description": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "exclude_label": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "exclude_type": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "external_contains": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "external_ref": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "gated": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "has_metadata_key": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "include_deferred": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "include_ephemeral": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "include_gates": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "include_infra": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "include_templates": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label_any": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label_pattern": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label_regex": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "metadata_field": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "mol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "mol_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "no_assignee": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "no_labels": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "no_parent": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "no_pinned": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "notes_contains": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "overdue": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "parent": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pinned": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "priority": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "priority_max": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "priority_min": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ready": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "spec": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "stale_days": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "status": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unassigned": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "updated_after": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "updated_before": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "wisp_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "Order": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "enum": [
            "priority",
            "created",
            "updated",
            "closed",
            "status",
            "id",
            "title",
            "type",
            "assignee"
          ],
          "type": "string"
        },
        "reverse": {
          "default": false,
          "type": "boolean"
        }
      },
      "required": [
        "field"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "cursor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expression": {
      "anyOf": [
        {
          "maxLength": 4000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Native Beads query, e.g. status=open AND priority<=1."
    },
    "filters": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Filter AST: field=value or field={op,value}; combine with and/or/not."
    },
    "graph": {
      "anyOf": [
        {
          "$ref": "#/$defs/GraphQuery"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Dependency graph walk from one bead instead of a list."
    },
    "includes": {
      "items": {
        "enum": [
          "comments",
          "history",
          "events",
          "dependencies",
          "dependents",
          "children",
          "refs",
          "blockers"
        ],
        "type": "string"
      },
      "maxItems": 8,
      "type": "array"
    },
    "limit": {
      "default": 50,
      "description": "Applied at the owner before any row is materialized.",
      "maximum": 200,
      "minimum": 1,
      "type": "integer"
    },
    "memory": {
      "anyOf": [
        {
          "$ref": "#/$defs/MemoryQuery"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Project memories instead of a list."
    },
    "native_filters": {
      "anyOf": [
        {
          "$ref": "#/$defs/NativeFilters"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "order": {
      "anyOf": [
        {
          "$ref": "#/$defs/Order"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "projects": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "maxItems": 32,
          "minItems": 1,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Project ids; omitted means every configured project (graph and memory need exactly one)."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "view": {
      "default": "query",
      "description": "query needs filters or expression; the other views are owner lists.",
      "enum": [
        "query",
        "ready",
        "blocked",
        "open",
        "all",
        "recent",
        "overdue",
        "deferred",
        "unassigned",
        "stale_claims",
        "epic_progress",
        "changed_since"
      ],
      "type": "string"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `BeadQuery`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.query` resource and `sinnix-agent-gateway catalog beads.query --schema`.

Examples:

Ready work in one project:

```json
{
  "limit": 10,
  "projects": [
    "sinnix"
  ],
  "view": "ready"
}
```

Open P0-P1 with dependencies:

```json
{
  "filters": {
    "priority": {
      "op": "<=",
      "value": 1
    },
    "status": "open"
  },
  "includes": [
    "dependencies"
  ],
  "projects": [
    "polylogue"
  ]
}
```

Title search:

```json
{
  "native_filters": {
    "title_contains": "gateway"
  },
  "projects": [
    "sinnix"
  ],
  "view": "open"
}
```

Dependency graph:

```json
{
  "graph": {
    "bead": "sinnix-abc1",
    "depth": 2,
    "direction": "both"
  },
  "projects": [
    "sinnix"
  ]
}
```

### `beads.get`

Read one bead by ref, id or title fragment, with optional comments, history, dependencies or graph.

Family: `get`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: show task, bd show, issue details, task notes.

Follow-up actions: `beads.change`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "BeadLocator": {
      "additionalProperties": false,
      "description": "A Beads task by canonical ref, id, or a title fragment within a project.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Bead id such as sinnix-abc1; the project is inferred from the prefix unless given."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/beads/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Case-insensitive title fragment; requires project and must match exactly one bead."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "as_of": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner history point (bd show --as-of)."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "graph_depth": {
      "default": 2,
      "maximum": 20,
      "minimum": 1,
      "type": "integer"
    },
    "includes": {
      "items": {
        "enum": [
          "comments",
          "history",
          "events",
          "dependencies",
          "dependents",
          "children",
          "refs",
          "blockers"
        ],
        "type": "string"
      },
      "maxItems": 8,
      "type": "array"
    },
    "projection": {
      "default": "summary",
      "description": "summary: the bead with requested includes; graph: also its dependency graph both ways; notes: only notes, description, design and acceptance.",
      "enum": [
        "summary",
        "graph",
        "notes"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/BeadLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Bead`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.get` resource and `sinnix-agent-gateway catalog beads.get --schema`.

Examples:

By id:

```json
{
  "includes": [
    "comments",
    "dependencies"
  ],
  "target": {
    "id": "sinnix-abc1"
  }
}
```

By title:

```json
{
  "projection": "notes",
  "target": {
    "project": "sinnix",
    "title_contains": "gateway overhaul"
  }
}
```

### `beads.change`

expected.expected_task_revision/expected_etag come from beads.get. Use mode=preview to see the compiled command and a preview_digest before applying.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: create task, close task, claim, comment, add note, bd update, bd close, block on.

Follow-up actions: `beads.get`, `beads.query`, `beads.changeset`.

Input schema:

```json
{
  "$defs": {
    "BeadLocator": {
      "additionalProperties": false,
      "description": "A Beads task by canonical ref, id, or a title fragment within a project.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Bead id such as sinnix-abc1; the project is inferred from the prefix unless given."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/beads/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Case-insensitive title fragment; requires project and must match exactly one bead."
        }
      },
      "type": "object"
    },
    "ClaimOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "claim",
          "default": "claim",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "CloseOp": {
      "additionalProperties": false,
      "properties": {
        "force": {
          "anyOf": [
            {
              "const": true,
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Close despite open blockers."
        },
        "operation": {
          "const": "close",
          "default": "close",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "CommentOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "comment",
          "default": "comment",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        },
        "text": {
          "maxLength": 32000,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "target",
        "text"
      ],
      "type": "object"
    },
    "CreateOp": {
      "additionalProperties": false,
      "properties": {
        "acceptance": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "assignee": {
          "anyOf": [
            {
              "maxLength": 256,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "defer": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "dependencies": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "description": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "design": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "due": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "external_ref": {
          "anyOf": [
            {
              "maxLength": 1000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "labels": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "notes": {
          "anyOf": [
            {
              "$ref": "#/$defs/Notes"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "operation": {
          "const": "create",
          "default": "create",
          "type": "string"
        },
        "parent": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "priority": {
          "anyOf": [
            {
              "maxLength": 8,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "0-4 or P0-P4."
        },
        "project": {
          "$ref": "#/$defs/ProjectLocator"
        },
        "spec_id": {
          "anyOf": [
            {
              "maxLength": 256,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "status": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title": {
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "project",
        "title"
      ],
      "type": "object"
    },
    "DependencyAddOp": {
      "additionalProperties": false,
      "properties": {
        "depends_on": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "dependency.add",
          "default": "dependency.add",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        },
        "type": {
          "default": "blocks",
          "maxLength": 64,
          "type": "string"
        }
      },
      "required": [
        "target",
        "depends_on"
      ],
      "type": "object"
    },
    "DependencyRemoveOp": {
      "additionalProperties": false,
      "properties": {
        "depends_on": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "dependency.remove",
          "default": "dependency.remove",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target",
        "depends_on"
      ],
      "type": "object"
    },
    "GraphCreateOp": {
      "additionalProperties": false,
      "properties": {
        "graph": {
          "additionalProperties": true,
          "description": "Native bd create --graph plan.",
          "minProperties": 1,
          "type": "object"
        },
        "operation": {
          "const": "graph.create",
          "default": "graph.create",
          "type": "string"
        },
        "project": {
          "$ref": "#/$defs/ProjectLocator"
        }
      },
      "required": [
        "project",
        "graph"
      ],
      "type": "object"
    },
    "LabelPatch": {
      "additionalProperties": false,
      "properties": {
        "add": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "remove": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "replace": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "MemoryForgetOp": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "memory.forget",
          "default": "memory.forget",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target",
        "key"
      ],
      "type": "object"
    },
    "MemoryRememberOp": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "memory.remember",
          "default": "memory.remember",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator",
          "description": "Bead the memory is attested against."
        },
        "text": {
          "maxLength": 32000,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "target",
        "key",
        "text"
      ],
      "type": "object"
    },
    "MetadataPatch": {
      "additionalProperties": false,
      "properties": {
        "set": {
          "anyOf": [
            {
              "additionalProperties": true,
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unset": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "Notes": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "default": "append",
          "enum": [
            "append",
            "replace"
          ],
          "type": "string"
        },
        "text": {
          "maxLength": 32000,
          "type": "string"
        }
      },
      "required": [
        "text"
      ],
      "type": "object"
    },
    "Patch": {
      "additionalProperties": false,
      "properties": {
        "labels": {
          "anyOf": [
            {
              "$ref": "#/$defs/LabelPatch"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "metadata": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataPatch"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "notes": {
          "anyOf": [
            {
              "$ref": "#/$defs/Notes"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "set": {
          "anyOf": [
            {
              "additionalProperties": true,
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Scalar fields: title, description, design, acceptance, status, priority, assignee, due, defer, estimate, external_ref, spec_id, parent."
        },
        "unset": {
          "anyOf": [
            {
              "items": {
                "enum": [
                  "due",
                  "defer",
                  "parent"
                ],
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "Preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_assignee": {
          "anyOf": [
            {
              "maxLength": 256,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_etag": {
          "anyOf": [
            {
              "pattern": "^[0-9a-f]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_status": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_task_revision": {
          "anyOf": [
            {
              "pattern": "^[0-9a-f]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    },
    "RelateOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "relate",
          "default": "relate",
          "type": "string"
        },
        "other_id": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target",
        "other_id"
      ],
      "type": "object"
    },
    "ReopenOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "reopen",
          "default": "reopen",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "ReparentOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "reparent",
          "default": "reparent",
          "type": "string"
        },
        "parent_id": {
          "default": "",
          "description": "Empty detaches from the parent.",
          "maxLength": 128,
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "UnclaimOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "unclaim",
          "default": "unclaim",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "maxLength": 32000,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "UnrelateOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "unrelate",
          "default": "unrelate",
          "type": "string"
        },
        "other_id": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target",
        "other_id"
      ],
      "type": "object"
    },
    "UpdateOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "update",
          "default": "update",
          "type": "string"
        },
        "patch": {
          "$ref": "#/$defs/Patch"
        },
        "target": {
          "$ref": "#/$defs/BeadLocator"
        }
      },
      "required": [
        "target",
        "patch"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "change": {
      "discriminator": {
        "mapping": {
          "claim": "#/$defs/ClaimOp",
          "close": "#/$defs/CloseOp",
          "comment": "#/$defs/CommentOp",
          "create": "#/$defs/CreateOp",
          "dependency.add": "#/$defs/DependencyAddOp",
          "dependency.remove": "#/$defs/DependencyRemoveOp",
          "graph.create": "#/$defs/GraphCreateOp",
          "memory.forget": "#/$defs/MemoryForgetOp",
          "memory.remember": "#/$defs/MemoryRememberOp",
          "relate": "#/$defs/RelateOp",
          "reopen": "#/$defs/ReopenOp",
          "reparent": "#/$defs/ReparentOp",
          "unclaim": "#/$defs/UnclaimOp",
          "unrelate": "#/$defs/UnrelateOp",
          "update": "#/$defs/UpdateOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/CreateOp"
        },
        {
          "$ref": "#/$defs/GraphCreateOp"
        },
        {
          "$ref": "#/$defs/UpdateOp"
        },
        {
          "$ref": "#/$defs/ClaimOp"
        },
        {
          "$ref": "#/$defs/UnclaimOp"
        },
        {
          "$ref": "#/$defs/CloseOp"
        },
        {
          "$ref": "#/$defs/ReopenOp"
        },
        {
          "$ref": "#/$defs/CommentOp"
        },
        {
          "$ref": "#/$defs/DependencyAddOp"
        },
        {
          "$ref": "#/$defs/DependencyRemoveOp"
        },
        {
          "$ref": "#/$defs/RelateOp"
        },
        {
          "$ref": "#/$defs/UnrelateOp"
        },
        {
          "$ref": "#/$defs/ReparentOp"
        },
        {
          "$ref": "#/$defs/MemoryRememberOp"
        },
        {
          "$ref": "#/$defs/MemoryForgetOp"
        }
      ]
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected": {
      "anyOf": [
        {
          "$ref": "#/$defs/Preconditions"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Typed preconditions; merged with preconditions."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "mode": {
      "default": "apply",
      "description": "preview compiles and dry-runs without writing and returns a preview_digest.",
      "enum": [
        "apply",
        "preview"
      ],
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "preview_digest": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "From a preview; apply is refused if the source moved since."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "idempotency_key",
    "change"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ChangeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.change` resource and `sinnix-agent-gateway catalog beads.change --schema`.

Examples:

Create:

```json
{
  "change": {
    "operation": "create",
    "priority": "2",
    "project": {
      "project": "sinnix"
    },
    "title": "Port beads actions",
    "type": "task"
  },
  "idempotency_key": "create-1"
}
```

Comment:

```json
{
  "change": {
    "operation": "comment",
    "target": {
      "id": "sinnix-abc1"
    },
    "text": "landed in gateway-overhaul"
  },
  "idempotency_key": "comment-1"
}
```

Close with reason:

```json
{
  "change": {
    "operation": "close",
    "reason": "shipped",
    "target": {
      "id": "sinnix-abc1"
    }
  },
  "expected": {
    "expected_status": "in_progress"
  },
  "idempotency_key": "close-1"
}
```

### `beads.changeset`

No global rollback: each applied step reports its outcome and a compensation hint. Preview first, then apply with the returned preview_digest.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: batch, bulk create, epic with children, several tasks.

Follow-up actions: `beads.query`, `beads.get`, `beads.change`.

Input schema:

```json
{
  "$defs": {
    "ChangesetStep": {
      "additionalProperties": false,
      "properties": {
        "bead": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target bead id, or a $symbol bound by an earlier step; omit for create, graph and memory operations."
        },
        "bind": {
          "anyOf": [
            {
              "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Name the created bead for later steps as $name."
        },
        "operation": {
          "enum": [
            "create",
            "graph.create",
            "update",
            "claim",
            "unclaim",
            "close",
            "reopen",
            "comment",
            "dependency.add",
            "dependency.remove",
            "relate",
            "unrelate",
            "reparent",
            "memory.remember",
            "memory.forget"
          ],
          "type": "string"
        },
        "parameters": {
          "additionalProperties": true,
          "description": "Operation fields as for beads.change (title, text, patch, ...); values may reference $symbols.",
          "type": "object"
        },
        "preconditions": {
          "anyOf": [
            {
              "$ref": "#/$defs/Preconditions"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id; defaults to the changeset project."
        }
      },
      "required": [
        "operation"
      ],
      "type": "object"
    },
    "Preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_assignee": {
          "anyOf": [
            {
              "maxLength": 256,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_etag": {
          "anyOf": [
            {
              "pattern": "^[0-9a-f]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_status": {
          "anyOf": [
            {
              "maxLength": 64,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_task_revision": {
          "anyOf": [
            {
              "pattern": "^[0-9a-f]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "mode": {
      "default": "preview",
      "enum": [
        "preview",
        "apply"
      ],
      "type": "string"
    },
    "on_error": {
      "default": "stop",
      "enum": [
        "stop",
        "continue"
      ],
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "preview_digest": {
      "anyOf": [
        {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "steps": {
      "items": {
        "$ref": "#/$defs/ChangesetStep"
      },
      "maxItems": 128,
      "minItems": 1,
      "type": "array"
    }
  },
  "required": [
    "idempotency_key",
    "project",
    "steps"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ChangesetResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.changeset` resource and `sinnix-agent-gateway catalog beads.changeset --schema`.

Examples:

Epic with one child:

```json
{
  "idempotency_key": "changeset-1",
  "project": {
    "project": "sinnix"
  },
  "steps": [
    {
      "bind": "epic",
      "operation": "create",
      "parameters": {
        "title": "Epic",
        "type": "epic"
      }
    },
    {
      "operation": "create",
      "parameters": {
        "parent": "$epic",
        "title": "Child"
      }
    }
  ]
}
```

### `beads.operate`

Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.

Family: `operate`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: bd sync, bd export, backup beads, restore beads.

Follow-up actions: `beads.query`, `projects.get`.

Input schema:

```json
{
  "$defs": {
    "BackupCreate": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "backup.create",
          "default": "backup.create",
          "type": "string"
        }
      },
      "type": "object"
    },
    "BackupList": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "backup.list",
          "default": "backup.list",
          "type": "string"
        }
      },
      "type": "object"
    },
    "BackupRestore": {
      "additionalProperties": false,
      "properties": {
        "backup_id": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "backup.restore",
          "default": "backup.restore",
          "type": "string"
        }
      },
      "required": [
        "backup_id"
      ],
      "type": "object"
    },
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    },
    "SnapshotPublish": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "snapshot.publish",
          "default": "snapshot.publish",
          "type": "string"
        }
      },
      "type": "object"
    },
    "SyncPull": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "sync.pull",
          "default": "sync.pull",
          "type": "string"
        }
      },
      "type": "object"
    },
    "SyncPush": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "sync.push",
          "default": "sync.push",
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "discriminator": {
        "mapping": {
          "backup.create": "#/$defs/BackupCreate",
          "backup.list": "#/$defs/BackupList",
          "backup.restore": "#/$defs/BackupRestore",
          "snapshot.publish": "#/$defs/SnapshotPublish",
          "sync.pull": "#/$defs/SyncPull",
          "sync.push": "#/$defs/SyncPush"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/SnapshotPublish"
        },
        {
          "$ref": "#/$defs/SyncPush"
        },
        {
          "$ref": "#/$defs/SyncPull"
        },
        {
          "$ref": "#/$defs/BackupCreate"
        },
        {
          "$ref": "#/$defs/BackupList"
        },
        {
          "$ref": "#/$defs/BackupRestore"
        }
      ]
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "idempotency_key",
    "project",
    "operation"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OperateResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.operate` resource and `sinnix-agent-gateway catalog beads.operate --schema`.

Examples:

Publish snapshot:

```json
{
  "idempotency_key": "publish-1",
  "operation": {
    "operation": "snapshot.publish"
  },
  "project": {
    "project": "sinnix"
  }
}
```

Restore a backup:

```json
{
  "idempotency_key": "restore-1",
  "operation": {
    "backup_id": "2026-09-01",
    "operation": "backup.restore"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `jobs.list`

List queued jobs (pueue tasks) newest first, optionally for one project.

Family: `query`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: queue, pueue status, running jobs, tasks.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.wait`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "cursor": {
      "anyOf": [
        {
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "limit": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "anyOf": [
        {
          "$ref": "#/$defs/ProjectLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Only jobs labelled with this project."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobPage`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.list` resource and `sinnix-agent-gateway catalog jobs.list --schema`.

Examples:

Newest 20 jobs:

```json
{
  "limit": 20
}
```

One project's jobs:

```json
{
  "project": {
    "project": "sinnix"
  }
}
```

### `jobs.get`

One job's state and bead binding, with its log range or typed result on request.

Family: `get`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: job status, job result, job output, phase.

Follow-up actions: `jobs.logs`, `jobs.wait`, `jobs.cancel`, `jobs.retry`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 262144,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "description": "Log byte offset.",
      "minimum": 0,
      "type": "integer"
    },
    "projection": {
      "default": "summary",
      "enum": [
        "summary",
        "log",
        "result"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/JobLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobDetail`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.get` resource and `sinnix-agent-gateway catalog jobs.get --schema`.

Examples:

Job summary:

```json
{
  "target": {
    "job_id": 41
  }
}
```

Typed result:

```json
{
  "projection": "result",
  "target": {
    "ref": "sinnix://jobs/41"
  }
}
```

### `jobs.logs`

A byte range of a job's bounded log (workload output, then the wrapper's stderr).

Family: `get`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: job log, tail, output, stdout.

Follow-up actions: `jobs.get`, `jobs.wait`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 262144,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/JobLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobLog`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.logs` resource and `sinnix-agent-gateway catalog jobs.logs --schema`.

Examples:

First 64 KB of a log:

```json
{
  "target": {
    "job_id": 41
  }
}
```

Continue from an offset:

```json
{
  "max_bytes": 64000,
  "offset": 64000,
  "target": {
    "ref": "sinnix://jobs/41"
  }
}
```

### `jobs.wait`

The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job.

Family: `wait`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: wait for job, block, until done.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/JobLocator"
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 300,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobWait`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.wait` resource and `sinnix-agent-gateway catalog jobs.wait --schema`.

Examples:

Wait a minute:

```json
{
  "target": {
    "job_id": 41
  },
  "timeout_seconds": 60
}
```

### `jobs.cancel`

Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.

Family: `operate`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: kill, stop job, abort.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.retry`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected_phase": {
      "anyOf": [
        {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Refuse unless the job is still in this phase (queued, running, ...)."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/JobLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `CancelResult`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.cancel` resource and `sinnix-agent-gateway catalog jobs.cancel --schema`.

Examples:

Cancel a running job:

```json
{
  "expected_phase": "running",
  "idempotency_key": "cancel-41",
  "target": {
    "job_id": 41
  }
}
```

### `jobs.retry`

Re-run a terminal job in place with the same launch input and id (pueue restart).

Family: `operate`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: restart, rerun, requeue.

Follow-up actions: `jobs.wait`, `jobs.get`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/JobLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobView`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.retry` resource and `sinnix-agent-gateway catalog jobs.retry --schema`.

Examples:

Retry job 41:

```json
{
  "idempotency_key": "retry-41",
  "target": {
    "job_id": 41
  }
}
```

### `operations.run`

Queue one project-declared operation in its declared pool on the root or a worktree.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: agentctl job start, run check, run lint, verify, build.

Follow-up actions: `jobs.wait`, `jobs.logs`, `jobs.get`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "checkout": {
      "$ref": "#/$defs/CheckoutLocator",
      "description": "The project (its configured root) or one of its worktrees."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "description": "A declared operation name.",
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "idempotency_key",
    "checkout",
    "operation"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobView`; the full envelope schema is the `sinnix://gateway/v2/actions/operations.run` resource and `sinnix-agent-gateway catalog operations.run --schema`.

Examples:

Run sinnix check:

```json
{
  "checkout": {
    "project": "sinnix"
  },
  "idempotency_key": "check-1",
  "operation": "check"
}
```

Run on a worktree:

```json
{
  "checkout": {
    "path": "/realm/worktrees/sinnix-example"
  },
  "idempotency_key": "lint-worktree-1",
  "operation": "lint"
}
```

### `shell.run`

cwd is confined to the checkout; the job's log carries the output.

Family: `run`. Owner: `systemd-jobs`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: exec, command, bash, run command.

Follow-up actions: `jobs.wait`, `jobs.logs`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "CheckoutLocator": {
      "additionalProperties": false,
      "description": "A project checkout by ref, project id (+ optional checkout id), or path.",
      "properties": {
        "checkout": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Checkout id from projects.get; omitted means the configured root."
        },
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a checkout (root or linked worktree)."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project ref (default checkout) or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "argv": {
      "items": {
        "type": "string"
      },
      "maxItems": 128,
      "minItems": 1,
      "type": "array"
    },
    "checkout": {
      "$ref": "#/$defs/CheckoutLocator"
    },
    "cwd": {
      "default": ".",
      "description": "Relative to the checkout; may not leave it.",
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "timeout_seconds": {
      "default": 3600,
      "maximum": 3600,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "idempotency_key",
    "checkout",
    "argv"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `JobView`; the full envelope schema is the `sinnix://gateway/v2/actions/shell.run` resource and `sinnix-agent-gateway catalog shell.run --schema`.

Examples:

git status in sinnix:

```json
{
  "argv": [
    "git",
    "status",
    "--short"
  ],
  "checkout": {
    "project": "sinnix"
  },
  "idempotency_key": "status-1",
  "timeout_seconds": 300
}
```

### `agent.for_bead`

backend, model and effort default to the bead's model policy. A bead that already has a worktree is refused with conflict.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: lane start, dispatch, agentctl lane start, work on bead.

Follow-up actions: `jobs.wait`, `jobs.logs`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "BeadLocator": {
      "additionalProperties": false,
      "description": "A Beads task by canonical ref, id, or a title fragment within a project.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Bead id such as sinnix-abc1; the project is inferred from the prefix unless given."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/beads/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Case-insensitive title fragment; requires project and must match exactly one bead."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "backend": {
      "anyOf": [
        {
          "enum": [
            "claude",
            "codex",
            "gemini",
            "grok",
            "antigravity"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Defaults to the bead's model policy."
    },
    "bead": {
      "$ref": "#/$defs/BeadLocator"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "effort": {
      "anyOf": [
        {
          "maxLength": 32,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "model": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "idempotency_key",
    "bead"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `LaneStarted`; the full envelope schema is the `sinnix://gateway/v2/actions/agent.for_bead` resource and `sinnix-agent-gateway catalog agent.for_bead --schema`.

Examples:

Start a lane:

```json
{
  "bead": {
    "id": "sinnix-abc1"
  },
  "idempotency_key": "lane-sinnix-abc1"
}
```

Pin the agent:

```json
{
  "backend": "codex",
  "bead": {
    "ref": "sinnix://projects/sinnix/beads/sinnix-abc1"
  },
  "effort": "high",
  "idempotency_key": "lane-sinnix-abc1-codex",
  "model": "gpt-5.6-terra"
}
```

### `wait.for`

Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token.

Family: `wait`. Owner: `waits`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: wait until, block until, poll, watch for.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.cancel`, `events.tail`.

Input schema:

```json
{
  "$defs": {
    "BeadLocator": {
      "additionalProperties": false,
      "description": "A Beads task by canonical ref, id, or a title fragment within a project.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Bead id such as sinnix-abc1; the project is inferred from the prefix unless given."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/beads/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Case-insensitive title fragment; requires project and must match exactly one bead."
        }
      },
      "type": "object"
    },
    "BeadRevision": {
      "additionalProperties": false,
      "properties": {
        "bead": {
          "$ref": "#/$defs/BeadLocator"
        },
        "kind": {
          "const": "bead_revision",
          "default": "bead_revision",
          "type": "string"
        },
        "revision": {
          "description": "task_revision to wait for.",
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "bead",
        "revision"
      ],
      "type": "object"
    },
    "BeadStatus": {
      "additionalProperties": false,
      "properties": {
        "bead": {
          "$ref": "#/$defs/BeadLocator"
        },
        "kind": {
          "const": "bead_status",
          "default": "bead_status",
          "type": "string"
        },
        "status": {
          "description": "e.g. open, in_progress, closed",
          "maxLength": 64,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "bead",
        "status"
      ],
      "type": "object"
    },
    "CaptureFreshness": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "capture_freshness",
          "default": "capture_freshness",
          "type": "string"
        },
        "lane": {
          "description": "Capture lane name.",
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "max_age_seconds": {
          "exclusiveMinimum": 0,
          "maximum": 86400,
          "type": "number"
        }
      },
      "required": [
        "lane",
        "max_age_seconds"
      ],
      "type": "object"
    },
    "FileExists": {
      "additionalProperties": false,
      "properties": {
        "exists": {
          "default": true,
          "description": "False waits for the path to disappear.",
          "type": "boolean"
        },
        "kind": {
          "const": "file_exists",
          "default": "file_exists",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/FileLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "FileHash": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "file_hash",
          "default": "file_hash",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/FileLocator"
        }
      },
      "required": [
        "target",
        "sha256"
      ],
      "type": "object"
    },
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    },
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    },
    "JobTerminal": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "job_terminal",
          "default": "job_terminal",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/JobLocator"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "ReceiptAppearance": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "receipt_appearance",
          "default": "receipt_appearance",
          "type": "string"
        },
        "receipt_id": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "receipt_id"
      ],
      "type": "object"
    },
    "TerminalOutput": {
      "additionalProperties": false,
      "properties": {
        "extent": {
          "default": "screen",
          "enum": [
            "last_cmd_output",
            "screen",
            "all"
          ],
          "type": "string"
        },
        "kind": {
          "const": "terminal_output",
          "default": "terminal_output",
          "type": "string"
        },
        "match": {
          "description": "kitty window match, e.g. id:3 or title:build",
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        },
        "pattern": {
          "description": "Regex searched in the captured text.",
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "match",
        "pattern"
      ],
      "type": "object"
    },
    "UnitState": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "unit_state",
          "default": "unit_state",
          "type": "string"
        },
        "manager": {
          "default": "system",
          "enum": [
            "system",
            "user"
          ],
          "type": "string"
        },
        "state": {
          "description": "active, inactive, failed, activating, ...",
          "maxLength": 32,
          "minLength": 1,
          "type": "string"
        },
        "unit": {
          "description": "systemd unit name, e.g. pueued.service",
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "unit",
        "state"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "condition": {
      "discriminator": {
        "mapping": {
          "bead_revision": "#/$defs/BeadRevision",
          "bead_status": "#/$defs/BeadStatus",
          "capture_freshness": "#/$defs/CaptureFreshness",
          "file_exists": "#/$defs/FileExists",
          "file_hash": "#/$defs/FileHash",
          "job_terminal": "#/$defs/JobTerminal",
          "receipt_appearance": "#/$defs/ReceiptAppearance",
          "terminal_output": "#/$defs/TerminalOutput",
          "unit_state": "#/$defs/UnitState"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/JobTerminal"
        },
        {
          "$ref": "#/$defs/BeadStatus"
        },
        {
          "$ref": "#/$defs/BeadRevision"
        },
        {
          "$ref": "#/$defs/UnitState"
        },
        {
          "$ref": "#/$defs/FileHash"
        },
        {
          "$ref": "#/$defs/FileExists"
        },
        {
          "$ref": "#/$defs/CaptureFreshness"
        },
        {
          "$ref": "#/$defs/ReceiptAppearance"
        },
        {
          "$ref": "#/$defs/TerminalOutput"
        }
      ]
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "poll_seconds": {
      "default": 0.25,
      "maximum": 5,
      "minimum": 0.01,
      "type": "number"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 300,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "condition"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `WaitResult`; the full envelope schema is the `sinnix://gateway/v2/actions/wait.for` resource and `sinnix-agent-gateway catalog wait.for --schema`.

Examples:

Wait for a job:

```json
{
  "condition": {
    "kind": "job_terminal",
    "target": {
      "job_id": 41
    }
  },
  "timeout_seconds": 120
}
```

Wait for a bead to close:

```json
{
  "condition": {
    "bead": {
      "id": "sinnix-abc1"
    },
    "kind": "bead_status",
    "status": "closed"
  }
}
```

Wait for a file to appear:

```json
{
  "condition": {
    "kind": "file_exists",
    "target": {
      "path": "/realm/tmp/work/out.png"
    }
  }
}
```

Wait for a unit to be active:

```json
{
  "condition": {
    "kind": "unit_state",
    "manager": "user",
    "state": "active",
    "unit": "pueued.service"
  }
}
```

### `events.tail`

Pass next_cursor back to continue; a cursor from another principal or project scope fails stale_cursor.

Family: `events`. Owner: `events`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: what happened, recent activity, audit log, changes since.

Follow-up actions: `wait.for`, `jobs.get`, `events.tail`.

Input schema:

```json
{
  "$defs": {
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "cursor": {
      "anyOf": [
        {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "next_cursor from the previous page."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "limit": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "projects": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/ProjectLocator"
          },
          "maxItems": 16,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Scope; defaults to every configured project."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `EventPage`; the full envelope schema is the `sinnix://gateway/v2/actions/events.tail` resource and `sinnix-agent-gateway catalog events.tail --schema`.

Examples:

Latest events:

```json
{
  "limit": 50
}
```

One project:

```json
{
  "limit": 100,
  "projects": [
    {
      "project": "sinnix"
    }
  ]
}
```

### `context.compose`

Each component is budgeted and isolated: an unavailable owner marks its component unavailable with a reason instead of failing the call. The snapshot is persisted under snapshot_ref.

Family: `context`. Owner: `context`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: orient, overview, situation, what is going on, triage, review job, incident.

Follow-up actions: `jobs.list`, `jobs.logs`, `agent.for_bead`, `events.tail`, `wait.for`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id.",
      "properties": {
        "job_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "pueue task id, as `agentctl job list` shows it."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://jobs/\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical job ref returned by a run or list."
        }
      },
      "type": "object"
    },
    "ProjectLocator": {
      "additionalProperties": false,
      "description": "A configured project by canonical ref, project id, or a path inside it.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path inside a project checkout."
        },
        "project": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Project id."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical project or checkout ref."
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "intent": {
      "enum": [
        "project.orientation",
        "project.triage",
        "job.review",
        "incident"
      ],
      "type": "string"
    },
    "job": {
      "anyOf": [
        {
          "$ref": "#/$defs/JobLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Required for job.review."
    },
    "project": {
      "anyOf": [
        {
          "$ref": "#/$defs/ProjectLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Required for project.orientation, project.triage and incident."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "intent"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ComposedContext`; the full envelope schema is the `sinnix://gateway/v2/actions/context.compose` resource and `sinnix-agent-gateway catalog context.compose --schema`.

Examples:

Orient in sinnix:

```json
{
  "intent": "project.orientation",
  "project": {
    "project": "sinnix"
  }
}
```

Review a job:

```json
{
  "intent": "job.review",
  "job": {
    "job_id": 41
  }
}
```

Incident overview:

```json
{
  "intent": "incident",
  "project": {
    "project": "sinnix"
  }
}
```

### `desktop.snapshot`

One observation of the desktop: monitors, workspaces, focus, every window with geometry, and a generation stamp.

Family: `status`. Owner: `desktop`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: windows, clients, workspaces, monitors, active window, what is on screen.

Follow-up actions: `desktop.screenshot`, `desktop.operate`, `desktop.tree`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "include_windows": {
      "default": true,
      "description": "Include every client.",
      "type": "boolean"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `DesktopSnapshot`; the full envelope schema is the `sinnix://gateway/v2/actions/desktop.snapshot` resource and `sinnix-agent-gateway catalog desktop.snapshot --schema`.

Examples:

Observe the desktop:

```json
{}
```

### `desktop.screenshot`

full captures the focused output through the HDR-aware screenshot owner; window/rect/monitor targets capture with grim. On HDR outputs a corrected SDR variant is produced and preferred for the image block.

Family: `query`. Owner: `desktop`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: screen capture, grab screen, picture of screen, capture window.

Follow-up actions: `desktop.snapshot`, `desktop.operate`, `artifacts.read`.

Input schema:

```json
{
  "$defs": {
    "ActiveWindowTarget": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "active_window",
          "default": "active_window",
          "type": "string"
        }
      },
      "type": "object"
    },
    "FullTarget": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "full",
          "default": "full",
          "type": "string"
        }
      },
      "type": "object"
    },
    "MonitorTarget": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "monitor",
          "default": "monitor",
          "type": "string"
        },
        "name": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "name"
      ],
      "type": "object"
    },
    "RectTarget": {
      "additionalProperties": false,
      "properties": {
        "height": {
          "minimum": 1,
          "type": "integer"
        },
        "kind": {
          "const": "rect",
          "default": "rect",
          "type": "string"
        },
        "width": {
          "minimum": 1,
          "type": "integer"
        },
        "x": {
          "type": "integer"
        },
        "y": {
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y",
        "width",
        "height"
      ],
      "type": "object"
    },
    "WindowLocator": {
      "additionalProperties": false,
      "description": "A Hyprland client by canonical ref, address, class/title, pid or focus.",
      "properties": {
        "active": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "true selects the focused window."
        },
        "address": {
          "anyOf": [
            {
              "pattern": "^0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "class": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact window class (may combine with title_contains)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://desktop/windows/0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "WindowTarget": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "window",
          "default": "window",
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "fix_hdr": {
      "default": true,
      "description": "Also produce an SDR-corrected variant on HDR outputs.",
      "type": "boolean"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "description": "full = focused output; monitor, window, active_window or rect.",
      "discriminator": {
        "mapping": {
          "active_window": "#/$defs/ActiveWindowTarget",
          "full": "#/$defs/FullTarget",
          "monitor": "#/$defs/MonitorTarget",
          "rect": "#/$defs/RectTarget",
          "window": "#/$defs/WindowTarget"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/FullTarget"
        },
        {
          "$ref": "#/$defs/MonitorTarget"
        },
        {
          "$ref": "#/$defs/WindowTarget"
        },
        {
          "$ref": "#/$defs/ActiveWindowTarget"
        },
        {
          "$ref": "#/$defs/RectTarget"
        }
      ]
    },
    "variant": {
      "default": "auto",
      "description": "Which file rides in the image block; auto prefers corrected.",
      "enum": [
        "auto",
        "raw",
        "corrected"
      ],
      "type": "string"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Screenshot`; the full envelope schema is the `sinnix://gateway/v2/actions/desktop.screenshot` resource and `sinnix-agent-gateway catalog desktop.screenshot --schema`.

Examples:

Focused output:

```json
{}
```

The active window:

```json
{
  "target": {
    "kind": "active_window"
  }
}
```

A window by class:

```json
{
  "target": {
    "kind": "window",
    "window": {
      "class": "kitty"
    }
  }
}
```

### `desktop.tree`

Fails unavailable when the pyatspi bindings are absent from the gateway environment; Chromium apps expose a tree only when launched with accessibility forced on.

Family: `query`. Owner: `desktop`. Principals: `observer, operator`. Typed failures: `conflict, invalid_request, not_found, owner_failed, unavailable`.

Aliases: accessibility tree, a11y, widgets, ui elements.

Follow-up actions: `desktop.operate`, `desktop.screenshot`.

Input schema:

```json
{
  "$defs": {
    "WindowLocator": {
      "additionalProperties": false,
      "description": "A Hyprland client by canonical ref, address, class/title, pid or focus.",
      "properties": {
        "active": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "true selects the focused window."
        },
        "address": {
          "anyOf": [
            {
              "pattern": "^0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "class": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact window class (may combine with title_contains)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://desktop/windows/0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_depth": {
      "default": 40,
      "maximum": 200,
      "minimum": 1,
      "type": "integer"
    },
    "max_nodes": {
      "default": 2000,
      "maximum": 50000,
      "minimum": 1,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "window": {
      "anyOf": [
        {
          "$ref": "#/$defs/WindowLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Defaults to the active window."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `AccessibleTree`; the full envelope schema is the `sinnix://gateway/v2/actions/desktop.tree` resource and `sinnix-agent-gateway catalog desktop.tree --schema`.

Examples:

Active window tree:

```json
{
  "max_depth": 10
}
```

### `desktop.operate`

Pointer clicks, drags and scrolls need a virtual pointer tool (ydotool) on the host and fail unavailable without one; cursor moves always work. Window targets are natural locators; ambiguity returns candidates.

Family: `operate`. Owner: `desktop`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: focus window, launch app, close window, click, type text, press key, xdg-open, hyprctl dispatch.

Follow-up actions: `desktop.snapshot`, `desktop.screenshot`, `desktop.tree`.

Input schema:

```json
{
  "$defs": {
    "ClickOp": {
      "additionalProperties": false,
      "properties": {
        "button": {
          "default": "left",
          "enum": [
            "left",
            "right",
            "middle"
          ],
          "type": "string"
        },
        "operation": {
          "const": "click",
          "default": "click",
          "type": "string"
        },
        "x": {
          "type": "integer"
        },
        "y": {
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y"
      ],
      "type": "object"
    },
    "CloseOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "close",
          "default": "close",
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window"
      ],
      "type": "object"
    },
    "DispatchOp": {
      "additionalProperties": false,
      "properties": {
        "expression": {
          "description": "Escape hatch: a Hyprland Lua dispatcher expression, e.g. hl.dsp.focus({ workspace = 3 }).",
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "dispatch",
          "default": "dispatch",
          "type": "string"
        }
      },
      "required": [
        "expression"
      ],
      "type": "object"
    },
    "DoubleClickOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "double_click",
          "default": "double_click",
          "type": "string"
        },
        "x": {
          "type": "integer"
        },
        "y": {
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y"
      ],
      "type": "object"
    },
    "DragOp": {
      "additionalProperties": false,
      "properties": {
        "from_x": {
          "type": "integer"
        },
        "from_y": {
          "type": "integer"
        },
        "operation": {
          "const": "drag",
          "default": "drag",
          "type": "string"
        },
        "to_x": {
          "type": "integer"
        },
        "to_y": {
          "type": "integer"
        }
      },
      "required": [
        "from_x",
        "from_y",
        "to_x",
        "to_y"
      ],
      "type": "object"
    },
    "FocusOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "focus",
          "default": "focus",
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window"
      ],
      "type": "object"
    },
    "KeyOp": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "XKB key name, e.g. Return.",
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "mods": {
          "default": "",
          "description": "e.g. CTRL, SUPER SHIFT",
          "maxLength": 128,
          "type": "string"
        },
        "operation": {
          "const": "key",
          "default": "key",
          "type": "string"
        },
        "window": {
          "anyOf": [
            {
              "$ref": "#/$defs/WindowLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    },
    "KeyStateOp": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "mods": {
          "default": "",
          "maxLength": 128,
          "type": "string"
        },
        "operation": {
          "const": "key_state",
          "default": "key_state",
          "type": "string"
        },
        "state": {
          "enum": [
            "down",
            "repeat",
            "up"
          ],
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "key",
        "state",
        "window"
      ],
      "type": "object"
    },
    "LaunchOp": {
      "additionalProperties": false,
      "properties": {
        "command": {
          "description": "Shell command line.",
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "launch",
          "default": "launch",
          "type": "string"
        },
        "timeout_seconds": {
          "default": 15,
          "maximum": 120,
          "minimum": 1,
          "type": "integer"
        },
        "wait_for": {
          "anyOf": [
            {
              "$ref": "#/$defs/WindowLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Wait for this window to appear after launching."
        }
      },
      "required": [
        "command"
      ],
      "type": "object"
    },
    "MoveOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "move",
          "default": "move",
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        },
        "x": {
          "type": "integer"
        },
        "y": {
          "type": "integer"
        }
      },
      "required": [
        "window",
        "x",
        "y"
      ],
      "type": "object"
    },
    "OpenOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "open",
          "default": "open",
          "type": "string"
        },
        "uri": {
          "description": "URL or path for xdg-open.",
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "uri"
      ],
      "type": "object"
    },
    "PasteOp": {
      "additionalProperties": false,
      "properties": {
        "enter": {
          "default": false,
          "type": "boolean"
        },
        "operation": {
          "const": "paste",
          "default": "paste",
          "type": "string"
        },
        "text": {
          "maxLength": 65536,
          "minLength": 1,
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window",
        "text"
      ],
      "type": "object"
    },
    "ResizeOp": {
      "additionalProperties": false,
      "properties": {
        "height": {
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "resize",
          "default": "resize",
          "type": "string"
        },
        "width": {
          "minimum": 1,
          "type": "integer"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window",
        "width",
        "height"
      ],
      "type": "object"
    },
    "RightClickOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "right_click",
          "default": "right_click",
          "type": "string"
        },
        "x": {
          "type": "integer"
        },
        "y": {
          "type": "integer"
        }
      },
      "required": [
        "x",
        "y"
      ],
      "type": "object"
    },
    "ScrollOp": {
      "additionalProperties": false,
      "properties": {
        "dx": {
          "default": 0,
          "type": "integer"
        },
        "dy": {
          "default": 0,
          "type": "integer"
        },
        "operation": {
          "const": "scroll",
          "default": "scroll",
          "type": "string"
        },
        "x": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Move the cursor here first."
        },
        "y": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "TypeOp": {
      "additionalProperties": false,
      "properties": {
        "delay_ms": {
          "default": 0,
          "maximum": 1000,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "type",
          "default": "type",
          "type": "string"
        },
        "text": {
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window",
        "text"
      ],
      "type": "object"
    },
    "WaitWindowOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "wait_window",
          "default": "wait_window",
          "type": "string"
        },
        "timeout_seconds": {
          "default": 15,
          "maximum": 300,
          "minimum": 1,
          "type": "integer"
        },
        "until": {
          "default": "present",
          "enum": [
            "present",
            "absent"
          ],
          "type": "string"
        },
        "window": {
          "$ref": "#/$defs/WindowLocator"
        }
      },
      "required": [
        "window"
      ],
      "type": "object"
    },
    "WindowLocator": {
      "additionalProperties": false,
      "description": "A Hyprland client by canonical ref, address, class/title, pid or focus.",
      "properties": {
        "active": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "true selects the focused window."
        },
        "address": {
          "anyOf": [
            {
              "pattern": "^0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "class": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact window class (may combine with title_contains)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://desktop/windows/0x[0-9a-f]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "action": {
      "discriminator": {
        "mapping": {
          "click": "#/$defs/ClickOp",
          "close": "#/$defs/CloseOp",
          "dispatch": "#/$defs/DispatchOp",
          "double_click": "#/$defs/DoubleClickOp",
          "drag": "#/$defs/DragOp",
          "focus": "#/$defs/FocusOp",
          "key": "#/$defs/KeyOp",
          "key_state": "#/$defs/KeyStateOp",
          "launch": "#/$defs/LaunchOp",
          "move": "#/$defs/MoveOp",
          "open": "#/$defs/OpenOp",
          "paste": "#/$defs/PasteOp",
          "resize": "#/$defs/ResizeOp",
          "right_click": "#/$defs/RightClickOp",
          "scroll": "#/$defs/ScrollOp",
          "type": "#/$defs/TypeOp",
          "wait_window": "#/$defs/WaitWindowOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/FocusOp"
        },
        {
          "$ref": "#/$defs/LaunchOp"
        },
        {
          "$ref": "#/$defs/CloseOp"
        },
        {
          "$ref": "#/$defs/MoveOp"
        },
        {
          "$ref": "#/$defs/ResizeOp"
        },
        {
          "$ref": "#/$defs/ClickOp"
        },
        {
          "$ref": "#/$defs/DoubleClickOp"
        },
        {
          "$ref": "#/$defs/RightClickOp"
        },
        {
          "$ref": "#/$defs/DragOp"
        },
        {
          "$ref": "#/$defs/ScrollOp"
        },
        {
          "$ref": "#/$defs/TypeOp"
        },
        {
          "$ref": "#/$defs/PasteOp"
        },
        {
          "$ref": "#/$defs/KeyOp"
        },
        {
          "$ref": "#/$defs/KeyStateOp"
        },
        {
          "$ref": "#/$defs/WaitWindowOp"
        },
        {
          "$ref": "#/$defs/OpenOp"
        },
        {
          "$ref": "#/$defs/DispatchOp"
        }
      ]
    },
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "idempotency_key",
    "action"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OperateResult`; the full envelope schema is the `sinnix://gateway/v2/actions/desktop.operate` resource and `sinnix-agent-gateway catalog desktop.operate --schema`.

Examples:

Focus a window by title:

```json
{
  "action": {
    "operation": "focus",
    "window": {
      "title_contains": "Codex"
    }
  },
  "idempotency_key": "focus-1"
}
```

Launch and wait:

```json
{
  "action": {
    "command": "kitty --class scratch",
    "operation": "launch",
    "wait_for": {
      "class": "scratch"
    }
  },
  "idempotency_key": "launch-1"
}
```

Ctrl+L in the active window:

```json
{
  "action": {
    "key": "L",
    "mods": "CTRL",
    "operation": "key"
  },
  "idempotency_key": "key-1"
}
```

### `terminals.list`

Every kitty window with its ref, title, cwd, shell pid, focus and foreground processes.

Family: `catalog`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: kitty windows, terminal inventory, shells.

Follow-up actions: `terminals.get`, `terminals.screen`, `terminals.send`, `terminals.open`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `TerminalListing`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.list` resource and `sinnix-agent-gateway catalog terminals.list --schema`.

Examples:

List terminals:

```json
{}
```

### `terminals.get`

Resolve one terminal by ref, kitty id, title, cwd, pid or focus.

Family: `get`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: find terminal, which terminal, focused terminal.

Follow-up actions: `terminals.screen`, `terminals.send`, `terminals.run`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Terminal`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.get` resource and `sinnix-agent-gateway catalog terminals.get --schema`.

Examples:

The focused terminal:

```json
{
  "target": {
    "focused": true
  }
}
```

### `terminals.screen`

The visible screen text of one terminal.

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: what does the terminal show, terminal contents, screen text.

Follow-up actions: `terminals.scrollback`, `terminals.send`, `terminals.wait`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "ansi": {
      "default": false,
      "description": "Keep ANSI styling escapes.",
      "type": "boolean"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `TerminalText`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.screen` resource and `sinnix-agent-gateway catalog terminals.screen --schema`.

Examples:

Screen of a titled terminal:

```json
{
  "target": {
    "title_contains": "Codex"
  }
}
```

### `terminals.scrollback`

The last N lines of a terminal's history, screen, or last command output.

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: history, last output, scroll back, command output.

Follow-up actions: `terminals.screen`, `terminals.send`, `terminals.wait`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "ansi": {
      "default": false,
      "type": "boolean"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "lines": {
      "default": 500,
      "description": "Last N lines returned.",
      "maximum": 100000,
      "minimum": 1,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "source": {
      "default": "history",
      "description": "history = screen plus scrollback; last_command = output of the last shell command.",
      "enum": [
        "screen",
        "history",
        "last_command"
      ],
      "type": "string"
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `TerminalText`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.scrollback` resource and `sinnix-agent-gateway catalog terminals.scrollback --schema`.

Examples:

Last 200 lines of history:

```json
{
  "lines": 200,
  "target": {
    "title_contains": "Codex"
  }
}
```

Output of the last command:

```json
{
  "source": "last_command",
  "target": {
    "title_contains": "Codex"
  }
}
```

### `terminals.processes`

Foreground processes of one terminal and whether its shell is at a prompt.

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: what is running, is it busy, terminal processes.

Follow-up actions: `terminals.wait`, `terminals.send`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `TerminalProcesses`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.processes` resource and `sinnix-agent-gateway catalog terminals.processes --schema`.

Examples:

Processes in a terminal:

```json
{
  "target": {
    "title_contains": "Codex"
  }
}
```

### `terminals.send`

Send text (optionally with Enter or bracketed paste) or key presses to one terminal.

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: type into terminal, press keys, ctrl+c, send text.

Follow-up actions: `terminals.wait`, `terminals.screen`, `terminals.scrollback`.

Input schema:

```json
{
  "$defs": {
    "KeysInput": {
      "additionalProperties": false,
      "properties": {
        "keys": {
          "description": "kitty key names, e.g. ctrl+c, enter, escape, tab.",
          "items": {
            "type": "string"
          },
          "maxItems": 16,
          "minItems": 1,
          "type": "array"
        },
        "kind": {
          "const": "keys",
          "default": "keys",
          "type": "string"
        }
      },
      "required": [
        "keys"
      ],
      "type": "object"
    },
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "TextInput": {
      "additionalProperties": false,
      "properties": {
        "bracketed_paste": {
          "default": false,
          "type": "boolean"
        },
        "enter": {
          "default": false,
          "description": "Press Enter after the text.",
          "type": "boolean"
        },
        "kind": {
          "const": "text",
          "default": "text",
          "type": "string"
        },
        "text": {
          "maxLength": 64000,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "text"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "input": {
      "discriminator": {
        "mapping": {
          "keys": "#/$defs/KeysInput",
          "text": "#/$defs/TextInput"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/TextInput"
        },
        {
          "$ref": "#/$defs/KeysInput"
        }
      ]
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "input"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SendResult`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.send` resource and `sinnix-agent-gateway catalog terminals.send --schema`.

Examples:

Send a line:

```json
{
  "idempotency_key": "send-1",
  "input": {
    "enter": true,
    "kind": "text",
    "text": "status"
  },
  "target": {
    "title_contains": "Codex"
  }
}
```

Interrupt:

```json
{
  "idempotency_key": "send-2",
  "input": {
    "keys": [
      "ctrl+c"
    ],
    "kind": "keys"
  },
  "target": {
    "title_contains": "Codex"
  }
}
```

### `terminals.run`

Completion and output rely on kitty shell integration (at_prompt, last_cmd_output). exit_status is reported only with capture_exit_status, which appends a visible marker to the command line.

Family: `run`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: execute in terminal, run command, shell command in kitty.

Follow-up actions: `terminals.scrollback`, `terminals.wait`, `terminals.send`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "capture_exit_status": {
      "default": false,
      "description": "Append an exit-status marker to the command line so the status is reported; the marker is visible in the terminal.",
      "type": "boolean"
    },
    "command": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      ],
      "description": "A shell command line, or an argv list that is shell-quoted for you."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    },
    "timeout_seconds": {
      "default": 60,
      "maximum": 3600,
      "minimum": 1,
      "type": "integer"
    },
    "wait": {
      "default": true,
      "description": "Wait until the shell is back at a prompt.",
      "type": "boolean"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "command"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `RunResult`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.run` resource and `sinnix-agent-gateway catalog terminals.run --schema`.

Examples:

Run and wait:

```json
{
  "command": [
    "git",
    "status"
  ],
  "idempotency_key": "run-1",
  "target": {
    "title_contains": "Codex"
  }
}
```

Run with exit status:

```json
{
  "capture_exit_status": true,
  "command": "make test",
  "idempotency_key": "run-2",
  "target": {
    "title_contains": "Codex"
  },
  "timeout_seconds": 600
}
```

### `terminals.wait`

Wait until a terminal is at its prompt, shows a regex, finishes a process, or changes title.

Family: `wait`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: wait for prompt, wait for output, wait until done.

Follow-up actions: `terminals.screen`, `terminals.scrollback`, `terminals.send`.

Input schema:

```json
{
  "$defs": {
    "ProcessExitCondition": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "process_exit",
          "default": "process_exit",
          "type": "string"
        },
        "pid": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Defaults to any foreground process besides the shell."
        }
      },
      "type": "object"
    },
    "PromptCondition": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "prompt",
          "default": "prompt",
          "type": "string"
        }
      },
      "type": "object"
    },
    "RegexCondition": {
      "additionalProperties": false,
      "properties": {
        "extent": {
          "default": "all",
          "enum": [
            "screen",
            "all",
            "selection",
            "last_cmd_output",
            "last_non_empty_output"
          ],
          "type": "string"
        },
        "kind": {
          "const": "regex",
          "default": "regex",
          "type": "string"
        },
        "pattern": {
          "description": "Extended regex (grep -E).",
          "maxLength": 2048,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "pattern"
      ],
      "type": "object"
    },
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "TitleCondition": {
      "additionalProperties": false,
      "properties": {
        "contains": {
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        },
        "kind": {
          "const": "title",
          "default": "title",
          "type": "string"
        }
      },
      "required": [
        "contains"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "condition": {
      "discriminator": {
        "mapping": {
          "process_exit": "#/$defs/ProcessExitCondition",
          "prompt": "#/$defs/PromptCondition",
          "regex": "#/$defs/RegexCondition"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/PromptCondition"
        },
        {
          "$ref": "#/$defs/RegexCondition"
        },
        {
          "$ref": "#/$defs/ProcessExitCondition"
        },
        {
          "$ref": "#/$defs/TitleCondition"
        }
      ]
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 3600,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "target",
    "condition"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `WaitResult`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.wait` resource and `sinnix-agent-gateway catalog terminals.wait --schema`.

Examples:

Wait for the prompt:

```json
{
  "condition": {
    "kind": "prompt"
  },
  "target": {
    "title_contains": "Codex"
  }
}
```

Wait for a pattern:

```json
{
  "condition": {
    "kind": "regex",
    "pattern": "done|completed"
  },
  "target": {
    "title_contains": "Codex"
  },
  "timeout_seconds": 120
}
```

### `terminals.focus`

Focus one kitty window.

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: switch to terminal, bring terminal to front.

Follow-up actions: `terminals.send`, `terminals.screen`.

Input schema:

```json
{
  "$defs": {
    "TerminalLocator": {
      "additionalProperties": false,
      "description": "A kitty window by canonical ref, kitty id, title, cwd, pid or focus.",
      "properties": {
        "cwd": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "focused": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kitty_id": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Shell pid of the window."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://terminals/[0-9]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/TerminalLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `FocusResult`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.focus` resource and `sinnix-agent-gateway catalog terminals.focus --schema`.

Examples:

Focus by title:

```json
{
  "idempotency_key": "focus-1",
  "target": {
    "title_contains": "Codex"
  }
}
```

### `terminals.open`

Open a new kitty window (OS window, split or tab) with an optional cwd and command; returns its ref.

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: new terminal, open kitty, spawn shell.

Follow-up actions: `terminals.send`, `terminals.run`, `terminals.screen`, `terminals.focus`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "command": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Command to run in the new window; the window stays open afterwards."
    },
    "cwd": {
      "anyOf": [
        {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "placement": {
      "default": "os_window",
      "description": "New OS window, a split in the active tab, or a new tab.",
      "enum": [
        "os_window",
        "window",
        "tab"
      ],
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "title": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "idempotency_key"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OpenResult`; the full envelope schema is the `sinnix://gateway/v2/actions/terminals.open` resource and `sinnix-agent-gateway catalog terminals.open --schema`.

Examples:

New window in a project:

```json
{
  "cwd": "/realm/project/sinnix",
  "idempotency_key": "open-1"
}
```

Run a command in a new tab:

```json
{
  "command": [
    "htop"
  ],
  "idempotency_key": "open-2",
  "placement": "tab"
}
```

### `browser.pages`

List every open Chrome page with its ref; flags the gateway-owned pages that can be read, captured or operated.

Family: `catalog`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: tabs, open pages, list tabs, what is open in chrome.

Follow-up actions: `browser.page`, `browser.operate`, `browser.screenshot`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "include": {
      "default": "pages",
      "description": "all_targets also lists workers, extensions and service workers.",
      "enum": [
        "pages",
        "all_targets"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `PageListing`; the full envelope schema is the `sinnix://gateway/v2/actions/browser.pages` resource and `sinnix-agent-gateway catalog browser.pages --schema`.

Examples:

List pages:

```json
{}
```

### `browser.page`

Element refs (g<generation>e<n>) are attached to the DOM for this snapshot; a later snapshot or reload replaces them, and a stale ref fails not_found.

Family: `get`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: page text, read page, page content, elements, links, forms.

Follow-up actions: `browser.operate`, `browser.screenshot`.

Input schema:

```json
{
  "$defs": {
    "PageLocator": {
      "additionalProperties": false,
      "description": "A browser page by canonical ref, CDP page id, url or title fragment.",
      "properties": {
        "page_id": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://browser/pages/[A-Za-z0-9_-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "url_contains": {
          "anyOf": [
            {
              "maxLength": 2048,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_elements": {
      "default": 300,
      "maximum": 5000,
      "minimum": 1,
      "type": "integer"
    },
    "max_text": {
      "default": 20000,
      "maximum": 1000000,
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/PageLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `PageSnapshot`; the full envelope schema is the `sinnix://gateway/v2/actions/browser.page` resource and `sinnix-agent-gateway catalog browser.page --schema`.

Examples:

Read a page:

```json
{
  "target": {
    "url_contains": "example.test"
  }
}
```

### `browser.screenshot`

Screenshot a gateway-owned page through CDP; the image rides in an image block and is retained as an artifact.

Family: `query`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: page screenshot, capture page, picture of the page.

Follow-up actions: `browser.page`, `browser.operate`, `artifacts.read`.

Input schema:

```json
{
  "$defs": {
    "PageLocator": {
      "additionalProperties": false,
      "description": "A browser page by canonical ref, CDP page id, url or title fragment.",
      "properties": {
        "page_id": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://browser/pages/[A-Za-z0-9_-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "url_contains": {
          "anyOf": [
            {
              "maxLength": 2048,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "full_page": {
      "default": false,
      "type": "boolean"
    },
    "image_format": {
      "default": "png",
      "enum": [
        "png",
        "jpeg"
      ],
      "type": "string"
    },
    "quality": {
      "anyOf": [
        {
          "maximum": 100,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/PageLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `BrowserScreenshot`; the full envelope schema is the `sinnix://gateway/v2/actions/browser.screenshot` resource and `sinnix-agent-gateway catalog browser.screenshot --schema`.

Examples:

Full-page PNG:

```json
{
  "full_page": true,
  "target": {
    "url_contains": "example.test"
  }
}
```

### `browser.operate`

Operator tabs are never accepted as targets, even when a locator matches one. Element targets take a snapshot ref or a CSS selector.

Family: `operate`. Owner: `browser`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: open url, click link, fill form, type in browser, press enter, download file, upload file, run javascript.

Follow-up actions: `browser.page`, `browser.screenshot`, `browser.pages`.

Input schema:

```json
{
  "$defs": {
    "BackOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "back",
          "default": "back",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ClickOp": {
      "additionalProperties": false,
      "properties": {
        "element": {
          "$ref": "#/$defs/ElementTarget"
        },
        "operation": {
          "const": "click",
          "default": "click",
          "type": "string"
        }
      },
      "required": [
        "element"
      ],
      "type": "object"
    },
    "CloseOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "close",
          "default": "close",
          "type": "string"
        }
      },
      "type": "object"
    },
    "DownloadOp": {
      "additionalProperties": false,
      "properties": {
        "destination": {
          "anyOf": [
            {
              "$ref": "#/$defs/FileLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Host file; default: a gateway capture artifact."
        },
        "operation": {
          "const": "download",
          "default": "download",
          "type": "string"
        },
        "url": {
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "url"
      ],
      "type": "object"
    },
    "ElementTarget": {
      "additionalProperties": false,
      "description": "An element by snapshot ref or CSS selector.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^g\\d+e\\d+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "selector": {
          "anyOf": [
            {
              "maxLength": 8192,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "EvaluateOp": {
      "additionalProperties": false,
      "properties": {
        "javascript": {
          "maxLength": 64000,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "evaluate",
          "default": "evaluate",
          "type": "string"
        },
        "timeout_seconds": {
          "default": 30,
          "maximum": 300,
          "minimum": 1,
          "type": "integer"
        },
        "until_truthy": {
          "default": false,
          "description": "Poll the expression until truthy.",
          "type": "boolean"
        }
      },
      "required": [
        "javascript"
      ],
      "type": "object"
    },
    "FileLocator": {
      "additionalProperties": false,
      "description": "A host file or directory by absolute path or canonical ref.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Absolute host path; ~ expands to the gateway user's home."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical host-file ref returned by an earlier call."
        }
      },
      "type": "object"
    },
    "FillOp": {
      "additionalProperties": false,
      "properties": {
        "element": {
          "$ref": "#/$defs/ElementTarget"
        },
        "operation": {
          "const": "fill",
          "default": "fill",
          "type": "string"
        },
        "value": {
          "maxLength": 64000,
          "type": "string"
        }
      },
      "required": [
        "element",
        "value"
      ],
      "type": "object"
    },
    "FocusOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "focus",
          "default": "focus",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ForwardOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "forward",
          "default": "forward",
          "type": "string"
        }
      },
      "type": "object"
    },
    "KeyOp": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Enter, Tab, Escape, ArrowDown, ... or one character.",
          "maxLength": 32,
          "minLength": 1,
          "type": "string"
        },
        "mods": {
          "items": {
            "enum": [
              "ctrl",
              "shift",
              "alt",
              "meta"
            ],
            "type": "string"
          },
          "type": "array"
        },
        "operation": {
          "const": "key",
          "default": "key",
          "type": "string"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    },
    "NavigateOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "navigate",
          "default": "navigate",
          "type": "string"
        },
        "url": {
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "url"
      ],
      "type": "object"
    },
    "NewOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "new",
          "default": "new",
          "type": "string"
        },
        "url": {
          "anyOf": [
            {
              "maxLength": 8192,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "PageLocator": {
      "additionalProperties": false,
      "description": "A browser page by canonical ref, CDP page id, url or title fragment.",
      "properties": {
        "page_id": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://browser/pages/[A-Za-z0-9_-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "title_contains": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "url_contains": {
          "anyOf": [
            {
              "maxLength": 2048,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    },
    "ReloadOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "reload",
          "default": "reload",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ScrollOp": {
      "additionalProperties": false,
      "properties": {
        "dx": {
          "default": 0,
          "type": "integer"
        },
        "dy": {
          "default": 0,
          "type": "integer"
        },
        "element": {
          "anyOf": [
            {
              "$ref": "#/$defs/ElementTarget"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Scroll this element into view instead of by offset."
        },
        "operation": {
          "const": "scroll",
          "default": "scroll",
          "type": "string"
        }
      },
      "type": "object"
    },
    "SubmitOp": {
      "additionalProperties": false,
      "properties": {
        "element": {
          "anyOf": [
            {
              "$ref": "#/$defs/ElementTarget"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A form or a field inside it; default: the first form."
        },
        "operation": {
          "const": "submit",
          "default": "submit",
          "type": "string"
        }
      },
      "type": "object"
    },
    "UploadOp": {
      "additionalProperties": false,
      "properties": {
        "element": {
          "$ref": "#/$defs/ElementTarget"
        },
        "files": {
          "items": {
            "$ref": "#/$defs/FileLocator"
          },
          "maxItems": 32,
          "minItems": 1,
          "type": "array"
        },
        "operation": {
          "const": "upload",
          "default": "upload",
          "type": "string"
        }
      },
      "required": [
        "element",
        "files"
      ],
      "type": "object"
    },
    "WaitOp": {
      "additionalProperties": false,
      "properties": {
        "for": {
          "enum": [
            "selector",
            "text",
            "navigation"
          ],
          "type": "string"
        },
        "operation": {
          "const": "wait",
          "default": "wait",
          "type": "string"
        },
        "timeout_seconds": {
          "default": 30,
          "maximum": 300,
          "minimum": 1,
          "type": "integer"
        },
        "value": {
          "anyOf": [
            {
              "maxLength": 8192,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Selector or text; for navigation, the URL fragment to reach (optional)."
        }
      },
      "required": [
        "for"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "action": {
      "discriminator": {
        "mapping": {
          "back": "#/$defs/BackOp",
          "click": "#/$defs/ClickOp",
          "close": "#/$defs/CloseOp",
          "download": "#/$defs/DownloadOp",
          "evaluate": "#/$defs/EvaluateOp",
          "fill": "#/$defs/FillOp",
          "focus": "#/$defs/FocusOp",
          "forward": "#/$defs/ForwardOp",
          "key": "#/$defs/KeyOp",
          "navigate": "#/$defs/NavigateOp",
          "new": "#/$defs/NewOp",
          "reload": "#/$defs/ReloadOp",
          "scroll": "#/$defs/ScrollOp",
          "submit": "#/$defs/SubmitOp",
          "upload": "#/$defs/UploadOp",
          "wait": "#/$defs/WaitOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/NavigateOp"
        },
        {
          "$ref": "#/$defs/BackOp"
        },
        {
          "$ref": "#/$defs/ForwardOp"
        },
        {
          "$ref": "#/$defs/ReloadOp"
        },
        {
          "$ref": "#/$defs/NewOp"
        },
        {
          "$ref": "#/$defs/CloseOp"
        },
        {
          "$ref": "#/$defs/FocusOp"
        },
        {
          "$ref": "#/$defs/ClickOp"
        },
        {
          "$ref": "#/$defs/FillOp"
        },
        {
          "$ref": "#/$defs/SubmitOp"
        },
        {
          "$ref": "#/$defs/ScrollOp"
        },
        {
          "$ref": "#/$defs/KeyOp"
        },
        {
          "$ref": "#/$defs/WaitOp"
        },
        {
          "$ref": "#/$defs/DownloadOp"
        },
        {
          "$ref": "#/$defs/UploadOp"
        },
        {
          "$ref": "#/$defs/EvaluateOp"
        }
      ]
    },
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "anyOf": [
        {
          "$ref": "#/$defs/PageLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Required for every operation except new."
    }
  },
  "required": [
    "idempotency_key",
    "action"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `BrowserOperateResult`; the full envelope schema is the `sinnix://gateway/v2/actions/browser.operate` resource and `sinnix-agent-gateway catalog browser.operate --schema`.

Examples:

Open an agent page:

```json
{
  "action": {
    "operation": "new",
    "url": "https://example.test"
  },
  "idempotency_key": "new-1"
}
```

Click by snapshot ref:

```json
{
  "action": {
    "element": {
      "ref": "g1e4"
    },
    "operation": "click"
  },
  "idempotency_key": "click-1",
  "target": {
    "url_contains": "example.test"
  }
}
```

Fill and submit:

```json
{
  "action": {
    "element": {
      "selector": "#q"
    },
    "operation": "fill",
    "value": "sinnix"
  },
  "idempotency_key": "fill-1",
  "target": {
    "url_contains": "example.test"
  }
}
```

Wait for text:

```json
{
  "action": {
    "for": "text",
    "operation": "wait",
    "value": "Results"
  },
  "idempotency_key": "wait-1",
  "target": {
    "url_contains": "example.test"
  }
}
```

### `machine.snapshot`

Each section carries its own availability and source; GPU and network report unavailable because no owner exposes them.

Family: `status`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: overview, health, how is the machine, system status, top.

Follow-up actions: `machine.query`, `machine.units.list`, `processes.list`, `machine.operate`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "incident_limit": {
      "default": 20,
      "maximum": 200,
      "minimum": 1,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "unit_limit": {
      "default": 50,
      "maximum": 200,
      "minimum": 1,
      "type": "integer"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `MachineSnapshot`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.snapshot` resource and `sinnix-agent-gateway catalog machine.snapshot --schema`.

Examples:

Machine overview:

```json
{}
```

### `machine.query`

Read one sinnix-observe section with cursor paging, or the ops-reducer revision (operation=actions).

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: observe, pressure, storage, workloads, slices, revision.

Follow-up actions: `machine.operate`, `machine.units.get`, `processes.get`, `artifacts.read`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "cursor": {
      "default": 0,
      "description": "Row cursor for units/workloads/slices/blocked_tasks.",
      "minimum": 0,
      "type": "integer"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "limit": {
      "default": 100,
      "maximum": 500,
      "minimum": 1,
      "type": "integer"
    },
    "operation": {
      "description": "One sinnix-observe section, or actions for the ops-reducer revision.",
      "enum": [
        "overview",
        "pressure",
        "runtime_inventory",
        "gateway",
        "browser",
        "storage",
        "ingestion",
        "units",
        "workloads",
        "slices",
        "blocked_tasks",
        "actions"
      ],
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "operation"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `MachineSection`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.query` resource and `sinnix-agent-gateway catalog machine.query --schema`.

Examples:

Units page:

```json
{
  "cursor": 0,
  "limit": 50,
  "operation": "units"
}
```

Ops revision:

```json
{
  "operation": "actions"
}
```

### `machine.units.list`

List systemd units of one manager with load/active/sub state and a canonical ref each.

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: systemctl list-units, services, timers, failed units.

Follow-up actions: `machine.units.get`, `machine.units.logs`, `machine.units.operate`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "include_inactive": {
      "default": true,
      "description": "Pass --all so loaded-but-inactive units appear.",
      "type": "boolean"
    },
    "limit": {
      "default": 200,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "pattern": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Glob on the unit name, e.g. sinnix-*.service"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "scope": {
      "default": "user",
      "enum": [
        "user",
        "system"
      ],
      "type": "string"
    },
    "state": {
      "default": "any",
      "enum": [
        "any",
        "active",
        "inactive",
        "failed",
        "activating",
        "deactivating"
      ],
      "type": "string"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `UnitsListing`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.units.list` resource and `sinnix-agent-gateway catalog machine.units.list --schema`.

Examples:

Failed user units:

```json
{
  "scope": "user",
  "state": "failed"
}
```

### `machine.units.get`

Describe one unit via systemctl show: states, main pid, cgroup, restarts, timestamps.

Family: `get`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: systemctl status, unit status, service status, is it running.

Follow-up actions: `machine.units.logs`, `machine.units.operate`, `processes.get`.

Input schema:

```json
{
  "$defs": {
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "properties": {
      "description": "systemctl show properties; empty means a standard set.",
      "items": {
        "type": "string"
      },
      "maxItems": 200,
      "type": "array"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/UnitLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `UnitDetail`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.units.get` resource and `sinnix-agent-gateway catalog machine.units.get --schema`.

Examples:

Describe polylogued:

```json
{
  "target": {
    "name": "polylogued",
    "scope": "user"
  }
}
```

### `machine.units.logs`

Journal entries for one unit (journalctl -o json), bounded by line count and bytes.

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: journalctl, logs, journal, why did it fail.

Follow-up actions: `machine.units.get`, `machine.units.operate`.

Input schema:

```json
{
  "$defs": {
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "grep": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Case-insensitive regex on MESSAGE."
    },
    "lines": {
      "default": 100,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 1048576,
      "minimum": 1,
      "type": "integer"
    },
    "priority": {
      "anyOf": [
        {
          "enum": [
            "emerg",
            "alert",
            "crit",
            "err",
            "warning",
            "notice",
            "info",
            "debug"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Highest priority level to include (journalctl -p)."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "since": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "journalctl --since expression, e.g. '-1h' or an RFC 3339 time."
    },
    "target": {
      "$ref": "#/$defs/UnitLocator"
    },
    "until": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `UnitLogs`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.units.logs` resource and `sinnix-agent-gateway catalog machine.units.logs --schema`.

Examples:

Last 50 lines:

```json
{
  "lines": 50,
  "since": "-1h",
  "target": {
    "name": "polylogued"
  }
}
```

### `machine.operate`

expected_revision must match machine.query operation=actions; the reducer receipt is verified against the submitted action and target.

Family: `operate`. Owner: `ops-reducer`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: restart service, freeze, thaw, park, set policy, interrupt job.

Follow-up actions: `machine.query`, `machine.units.get`, `audit.receipt`.

Input schema:

```json
{
  "$defs": {
    "FreezeOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "freeze",
          "default": "freeze",
          "type": "string"
        }
      },
      "type": "object"
    },
    "InterruptOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "interrupt",
          "default": "interrupt",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ParkOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "park",
          "default": "park",
          "type": "string"
        },
        "deadline_seconds": {
          "maximum": 86400,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "deadline_seconds"
      ],
      "type": "object"
    },
    "RebuildOverrideOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "rebuild_override",
          "default": "rebuild_override",
          "type": "string"
        },
        "name": {
          "enum": [
            "max_jobs",
            "cores",
            "eval_cache"
          ],
          "type": "string"
        },
        "value": {
          "maxLength": 32,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "name",
        "value"
      ],
      "type": "object"
    },
    "ResetPolicyOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "reset_policy",
          "default": "reset_policy",
          "type": "string"
        }
      },
      "type": "object"
    },
    "RestartOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "restart",
          "default": "restart",
          "type": "string"
        }
      },
      "type": "object"
    },
    "SetPolicyOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "set_policy",
          "default": "set_policy",
          "type": "string"
        },
        "property": {
          "enum": [
            "MemoryHigh",
            "MemoryMax",
            "MemoryLow",
            "CPUWeight",
            "IOWeight",
            "Nice"
          ],
          "type": "string"
        },
        "value": {
          "maxLength": 64,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "property",
        "value"
      ],
      "type": "object"
    },
    "StartOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "start",
          "default": "start",
          "type": "string"
        }
      },
      "type": "object"
    },
    "StopOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "stop",
          "default": "stop",
          "type": "string"
        }
      },
      "type": "object"
    },
    "ThawOp": {
      "additionalProperties": false,
      "properties": {
        "action": {
          "const": "thaw",
          "default": "thaw",
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected_revision": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Revision from machine.query operation=actions; also accepted as preconditions.expected_revision."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "description": "The reducer action and its parameters.",
      "discriminator": {
        "mapping": {
          "freeze": "#/$defs/FreezeOp",
          "interrupt": "#/$defs/InterruptOp",
          "park": "#/$defs/ParkOp",
          "rebuild_override": "#/$defs/RebuildOverrideOp",
          "reset_policy": "#/$defs/ResetPolicyOp",
          "restart": "#/$defs/RestartOp",
          "set_policy": "#/$defs/SetPolicyOp",
          "start": "#/$defs/StartOp",
          "stop": "#/$defs/StopOp",
          "thaw": "#/$defs/ThawOp"
        },
        "propertyName": "action"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/InterruptOp"
        },
        {
          "$ref": "#/$defs/FreezeOp"
        },
        {
          "$ref": "#/$defs/ThawOp"
        },
        {
          "$ref": "#/$defs/ResetPolicyOp"
        },
        {
          "$ref": "#/$defs/SetPolicyOp"
        },
        {
          "$ref": "#/$defs/ParkOp"
        },
        {
          "$ref": "#/$defs/RebuildOverrideOp"
        },
        {
          "$ref": "#/$defs/RestartOp"
        },
        {
          "$ref": "#/$defs/StartOp"
        },
        {
          "$ref": "#/$defs/StopOp"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "description": "Canonical job, unit or process ref.",
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://(?:jobs|machine/units|processes)/",
      "type": "string"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "request"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OperateResult`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.operate` resource and `sinnix-agent-gateway catalog machine.operate --schema`.

Examples:

Restart a unit:

```json
{
  "expected_revision": 42,
  "idempotency_key": "restart-example",
  "reason": "apply the approved restart",
  "request": {
    "action": "restart"
  },
  "target": "sinnix://machine/units/user/example.service"
}
```

Cap a unit's memory:

```json
{
  "expected_revision": 42,
  "idempotency_key": "policy-example",
  "reason": "bound the runaway",
  "request": {
    "action": "set_policy",
    "property": "MemoryHigh",
    "value": "4G"
  },
  "target": "sinnix://machine/units/user/example.service"
}
```

### `machine.units.operate`

Start, stop or restart one unit through the ops reducer (reload and wait are not reducer actions).

Family: `operate`. Owner: `ops-reducer`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: systemctl restart, systemctl start, systemctl stop, bounce.

Follow-up actions: `machine.units.get`, `machine.units.logs`, `audit.receipt`.

Input schema:

```json
{
  "$defs": {
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "action": {
      "enum": [
        "start",
        "stop",
        "restart"
      ],
      "type": "string"
    },
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "expected_revision": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/UnitLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "action"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OperateResult`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.units.operate` resource and `sinnix-agent-gateway catalog machine.units.operate --schema`.

Examples:

Restart by name:

```json
{
  "action": "restart",
  "expected_revision": 42,
  "idempotency_key": "restart-example-2",
  "reason": "apply config",
  "target": {
    "name": "example",
    "scope": "user"
  }
}
```

### `processes.list`

List live processes filtered by name, pid, unit, cgroup or user, with a canonical ref each.

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: ps, pgrep, what is running, find process.

Follow-up actions: `processes.get`, `processes.tree`, `processes.signal`, `machine.units.get`.

Input schema:

```json
{
  "$defs": {
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "cgroup": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Substring of the cgroup path, e.g. agent.slice."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "limit": {
      "default": 200,
      "maximum": 5000,
      "minimum": 1,
      "type": "integer"
    },
    "name": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Substring of comm or cmdline (case-insensitive)."
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "pid": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "unit": {
      "anyOf": [
        {
          "$ref": "#/$defs/UnitLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "user": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "with_cmdline": {
      "default": true,
      "type": "boolean"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProcessListing`; the full envelope schema is the `sinnix://gateway/v2/actions/processes.list` resource and `sinnix-agent-gateway catalog processes.list --schema`.

Examples:

Processes named rg:

```json
{
  "name": "rg"
}
```

Processes of a unit:

```json
{
  "unit": {
    "name": "polylogued"
  }
}
```

### `processes.get`

Describe one process: cmdline, cwd, exe, redacted env, cgroup/unit, parent, children, sockets, cpu and memory.

Family: `get`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: process info, pid details, what is pid, open sockets, environment.

Follow-up actions: `processes.tree`, `processes.signal`, `processes.wait`, `machine.units.get`.

Input schema:

```json
{
  "$defs": {
    "ProcessLocator": {
      "additionalProperties": false,
      "description": "A live process by canonical ref, pid, executable name or owning unit.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact kernel comm (executable base name, 15 chars max)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://processes/[0-9]{1,10}/[0-9]{1,20}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unit": {
          "anyOf": [
            {
              "$ref": "#/$defs/UnitLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The systemd unit whose cgroup owns the process."
        }
      },
      "type": "object"
    },
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "env_limit": {
      "default": 500,
      "maximum": 5000,
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ProcessLocator"
    },
    "with_env": {
      "default": true,
      "type": "boolean"
    },
    "with_sockets": {
      "default": true,
      "type": "boolean"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProcessDetail`; the full envelope schema is the `sinnix://gateway/v2/actions/processes.get` resource and `sinnix-agent-gateway catalog processes.get --schema`.

Examples:

Inspect pid 1234:

```json
{
  "target": {
    "pid": 1234
  }
}
```

### `processes.tree`

Parent/child process tree from one root or from every top-level process, bounded by depth and node count.

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: pstree, children, descendants.

Follow-up actions: `processes.get`, `processes.signal`.

Input schema:

```json
{
  "$defs": {
    "ProcessLocator": {
      "additionalProperties": false,
      "description": "A live process by canonical ref, pid, executable name or owning unit.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact kernel comm (executable base name, 15 chars max)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://processes/[0-9]{1,10}/[0-9]{1,20}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unit": {
          "anyOf": [
            {
              "$ref": "#/$defs/UnitLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The systemd unit whose cgroup owns the process."
        }
      },
      "type": "object"
    },
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_depth": {
      "default": 6,
      "maximum": 32,
      "minimum": 1,
      "type": "integer"
    },
    "max_nodes": {
      "default": 500,
      "maximum": 5000,
      "minimum": 1,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "root": {
      "anyOf": [
        {
          "$ref": "#/$defs/ProcessLocator"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Subtree root; omitted means every process without a live parent."
    },
    "with_cmdline": {
      "default": false,
      "type": "boolean"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `ProcessTree`; the full envelope schema is the `sinnix://gateway/v2/actions/processes.tree` resource and `sinnix-agent-gateway catalog processes.tree --schema`.

Examples:

Subtree of a unit's main process:

```json
{
  "max_depth": 4,
  "root": {
    "unit": {
      "name": "polylogued"
    }
  }
}
```

### `processes.signal`

The reducer path is the attested one and needs expected_revision; the direct path is receipted by the gateway audit chain only.

Family: `operate`. Owner: `machine`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: kill, pkill, terminate, sigterm, sigkill.

Follow-up actions: `processes.wait`, `processes.get`, `audit.receipt`.

Input schema:

```json
{
  "$defs": {
    "DirectSignal": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "signal",
          "default": "signal",
          "type": "string"
        },
        "signal": {
          "default": "TERM",
          "enum": [
            "TERM",
            "KILL",
            "INT",
            "HUP",
            "USR1",
            "USR2",
            "STOP",
            "CONT",
            "QUIT"
          ],
          "type": "string"
        }
      },
      "type": "object"
    },
    "ProcessLocator": {
      "additionalProperties": false,
      "description": "A live process by canonical ref, pid, executable name or owning unit.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact kernel comm (executable base name, 15 chars max)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://processes/[0-9]{1,10}/[0-9]{1,20}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unit": {
          "anyOf": [
            {
              "$ref": "#/$defs/UnitLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The systemd unit whose cgroup owns the process."
        }
      },
      "type": "object"
    },
    "ReducerStop": {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "description": "Revision from machine.query operation=actions.",
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "stop",
          "default": "stop",
          "type": "string"
        }
      },
      "required": [
        "expected_revision"
      ],
      "type": "object"
    },
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "description": "stop: attested SIGTERM/SIGKILL through the ops reducer (admitted slices only). signal: direct os.kill by the operator.",
      "discriminator": {
        "mapping": {
          "signal": "#/$defs/DirectSignal",
          "stop": "#/$defs/ReducerStop"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/ReducerStop"
        },
        {
          "$ref": "#/$defs/DirectSignal"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ProcessLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "request"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SignalResult`; the full envelope schema is the `sinnix://gateway/v2/actions/processes.signal` resource and `sinnix-agent-gateway catalog processes.signal --schema`.

Examples:

Reducer stop:

```json
{
  "idempotency_key": "stop-4242",
  "reason": "runaway rg",
  "request": {
    "expected_revision": 17,
    "operation": "stop"
  },
  "target": {
    "pid": 4242
  }
}
```

Direct SIGHUP:

```json
{
  "idempotency_key": "hup-kitty-1",
  "reason": "reload config",
  "request": {
    "operation": "signal",
    "signal": "HUP"
  },
  "target": {
    "name": "kitty"
  }
}
```

### `processes.wait`

Wait until a process (same pid and start ticks) exits, or the bounded timeout elapses.

Family: `wait`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: wait for exit, await process, has it finished.

Follow-up actions: `processes.get`, `processes.signal`, `processes.list`.

Input schema:

```json
{
  "$defs": {
    "ProcessLocator": {
      "additionalProperties": false,
      "description": "A live process by canonical ref, pid, executable name or owning unit.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact kernel comm (executable base name, 15 chars max)."
        },
        "pid": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://processes/[0-9]{1,10}/[0-9]{1,20}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "unit": {
          "anyOf": [
            {
              "$ref": "#/$defs/UnitLocator"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The systemd unit whose cgroup owns the process."
        }
      },
      "type": "object"
    },
    "UnitLocator": {
      "additionalProperties": false,
      "description": "A systemd unit by canonical ref or by name and manager scope.",
      "properties": {
        "name": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Unit name; a bare name without a type suffix means <name>.service."
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://machine/units/(user|system)/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Canonical unit ref: sinnix://machine/units/<user|system>/<unit>."
        },
        "scope": {
          "default": "user",
          "description": "Manager owning the unit.",
          "enum": [
            "user",
            "system"
          ],
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "poll_seconds": {
      "default": 0.2,
      "maximum": 5,
      "minimum": 0.01,
      "type": "number"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ProcessLocator"
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 300,
      "minimum": 0,
      "type": "number"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `WaitResult`; the full envelope schema is the `sinnix://gateway/v2/actions/processes.wait` resource and `sinnix-agent-gateway catalog processes.wait --schema`.

Examples:

Wait up to 10 s:

```json
{
  "target": {
    "pid": 4242
  },
  "timeout_seconds": 10
}
```

### `mcp.servers`

Each probe runs initialize + tools/list with a 5 s bound; a timeout stores the upstream stderr as an artifact and returns its ref.

Family: `status`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: mcp health, is polylogue mcp up, upstream servers, broker status.

Follow-up actions: `mcp.tools`, `mcp.call`, `artifacts.read`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "servers": {
      "description": "Probe only these configured servers; empty probes all.",
      "items": {
        "type": "string"
      },
      "maxItems": 32,
      "type": "array"
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Servers`; the full envelope schema is the `sinnix://gateway/v2/actions/mcp.servers` resource and `sinnix-agent-gateway catalog mcp.servers --schema`.

Examples:

Probe one server:

```json
{
  "servers": [
    "polylogue"
  ]
}
```

Probe all:

```json
{}
```

### `mcp.tools`

Catalog of every admitted upstream tool with its namespaced ref, input schema and read/change effect.

Family: `catalog`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: list mcp tools, upstream tools, tool schema.

Follow-up actions: `mcp.call`, `mcp.change`, `mcp.servers`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "effect": {
      "default": "any",
      "enum": [
        "any",
        "read",
        "change"
      ],
      "type": "string"
    },
    "include_schema": {
      "default": true,
      "type": "boolean"
    },
    "limit": {
      "default": 200,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "server": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "text": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Terms matched against name, description and server."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Tools`; the full envelope schema is the `sinnix://gateway/v2/actions/mcp.tools` resource and `sinnix-agent-gateway catalog mcp.tools --schema`.

Examples:

Read tools mentioning search:

```json
{
  "effect": "read",
  "text": "search"
}
```

### `mcp.call`

Tools without a read-only annotation are refused here; use mcp.change (operator only).

Family: `query`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: call mcp tool, query upstream, polylogue search.

Follow-up actions: `mcp.tools`, `artifacts.read`.

Input schema:

```json
{
  "$defs": {
    "McpToolLocator": {
      "additionalProperties": false,
      "description": "A brokered upstream MCP tool by canonical ref or server and tool name.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://mcp/[^/]{1,128}/tools/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "server": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "tool": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "arguments": {
      "additionalProperties": true,
      "description": "Arguments matching the tool's input_schema from mcp.tools.",
      "type": "object"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/McpToolLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `CallResult`; the full envelope schema is the `sinnix://gateway/v2/actions/mcp.call` resource and `sinnix-agent-gateway catalog mcp.call --schema`.

Examples:

Call by server and tool:

```json
{
  "arguments": {
    "query": "gateway"
  },
  "target": {
    "server": "polylogue",
    "tool": "search"
  }
}
```

### `mcp.change`

Invoke one upstream tool that is not declared read-only.

Family: `change`. Owner: `mcp-broker`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: write mcp tool, mutate upstream, refresh.

Follow-up actions: `mcp.tools`, `artifacts.read`, `audit.receipt`.

Input schema:

```json
{
  "$defs": {
    "McpToolLocator": {
      "additionalProperties": false,
      "description": "A brokered upstream MCP tool by canonical ref or server and tool name.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://mcp/[^/]{1,128}/tools/[^/]{1,256}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "server": {
          "anyOf": [
            {
              "maxLength": 128,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "tool": {
          "anyOf": [
            {
              "maxLength": 256,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "arguments": {
      "additionalProperties": true,
      "type": "object"
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "idempotency_key": {
      "description": "Replaying the same key with the same request returns the stored response.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Owner-checked preconditions; a mismatch fails with precondition_failed."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/McpToolLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `CallResult`; the full envelope schema is the `sinnix://gateway/v2/actions/mcp.change` resource and `sinnix-agent-gateway catalog mcp.change --schema`.

Examples:

Call a write tool:

```json
{
  "arguments": {},
  "idempotency_key": "mcp-refresh-example",
  "target": {
    "ref": "sinnix://mcp/lynchpin/tools/refresh"
  }
}
```

### `artifacts.list`

List principal-visible artifacts with kind, owner, size and canonical ref.

Family: `catalog`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: captures, diagnostics, stored responses, large results.

Follow-up actions: `artifacts.get`, `artifacts.read`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "kind": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Exact artifact kind, e.g. mcp-stderr, machine-query."
    },
    "limit": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "owner_id": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Listing`; the full envelope schema is the `sinnix://gateway/v2/actions/artifacts.list` resource and `sinnix-agent-gateway catalog artifacts.list --schema`.

Examples:

Recent MCP stderr captures:

```json
{
  "kind": "mcp-stderr",
  "limit": 20
}
```

### `artifacts.get`

Metadata of one artifact without its bytes.

Family: `get`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: artifact info, artifact metadata.

Follow-up actions: `artifacts.read`, `artifacts.list`.

Input schema:

```json
{
  "$defs": {
    "ArtifactLocator": {
      "additionalProperties": false,
      "description": "A gateway artifact by canonical ref or bare artifact id.",
      "properties": {
        "artifact_id": {
          "anyOf": [
            {
              "maxLength": 36,
              "minLength": 36,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://artifacts/[0-9a-fA-F-]{36}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ArtifactLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Metadata`; the full envelope schema is the `sinnix://gateway/v2/actions/artifacts.get` resource and `sinnix-agent-gateway catalog artifacts.get --schema`.

Examples:

By ref:

```json
{
  "target": {
    "ref": "sinnix://artifacts/00000000-0000-0000-0000-000000000000"
  }
}
```

### `artifacts.read`

Read an artifact: text inline with offsets, images as an image block, other binary as a resource block.

Family: `query`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: open artifact, diagnostic log, truncated response, view capture.

Follow-up actions: `artifacts.get`, `artifacts.list`.

Input schema:

```json
{
  "$defs": {
    "ArtifactLocator": {
      "additionalProperties": false,
      "description": "A gateway artifact by canonical ref or bare artifact id.",
      "properties": {
        "artifact_id": {
          "anyOf": [
            {
              "maxLength": 36,
              "minLength": 36,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://artifacts/[0-9a-fA-F-]{36}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 4194304,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "description": "Byte offset for text reads.",
      "minimum": 0,
      "type": "integer"
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "representation": {
      "default": "auto",
      "enum": [
        "auto",
        "text",
        "binary"
      ],
      "type": "string"
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "target": {
      "$ref": "#/$defs/ArtifactLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `Content`; the full envelope schema is the `sinnix://gateway/v2/actions/artifacts.read` resource and `sinnix-agent-gateway catalog artifacts.read --schema`.

Examples:

First 64 KB of a stored response:

```json
{
  "target": {
    "artifact_id": "00000000-0000-0000-0000-000000000000"
  }
}
```

### `captures.query`

List runtime-declared capture lanes, describe one, or read per-lane record deltas since a time.

Family: `query`. Owner: `captures`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: capture lanes, lane health, records since, sidecar index.

Follow-up actions: `activity.query`, `captures.query`.

Input schema:

```json
{
  "$defs": {
    "DeltaOp": {
      "additionalProperties": false,
      "properties": {
        "lanes": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Lane names; omitted means every visible lane."
        },
        "limit": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "query",
          "default": "query",
          "type": "string"
        },
        "since": {
          "default": 0.0,
          "description": "Unix seconds; counts records at or after this time.",
          "minimum": 0,
          "type": "number"
        }
      },
      "type": "object"
    },
    "LaneOp": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "lane",
          "default": "lane",
          "type": "string"
        }
      },
      "required": [
        "name"
      ],
      "type": "object"
    },
    "LanesOp": {
      "additionalProperties": false,
      "properties": {
        "operation": {
          "const": "lanes",
          "default": "lanes",
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "discriminator": {
        "mapping": {
          "lane": "#/$defs/LaneOp",
          "lanes": "#/$defs/LanesOp",
          "query": "#/$defs/DeltaOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/LanesOp"
        },
        {
          "$ref": "#/$defs/LaneOp"
        },
        {
          "$ref": "#/$defs/DeltaOp"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `CapturesResult`; the full envelope schema is the `sinnix://gateway/v2/actions/captures.query` resource and `sinnix-agent-gateway catalog captures.query --schema`.

Examples:

Visible lanes:

```json
{}
```

Deltas for two lanes:

```json
{
  "request": {
    "lanes": [
      "clipboard",
      "mpris"
    ],
    "operation": "query",
    "since": 1700000000
  }
}
```

### `activity.query`

Reads sinnix-capture-v1 envelope files under each lane path within the time window; coverage lists which lanes contributed and which have no envelope files.

Family: `query`. Owner: `captures`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: what was I doing, recent activity, clipboard history, notifications, now playing.

Follow-up actions: `captures.query`, `sessions.query`, `timeline.query`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "application": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Substring of the window class, app name or player."
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "kinds": {
      "description": "Lane names or payload event names, e.g. clipboard, notifications, heartbeat.",
      "items": {
        "type": "string"
      },
      "maxItems": 32,
      "type": "array"
    },
    "limit": {
      "default": 200,
      "maximum": 2000,
      "minimum": 1,
      "type": "integer"
    },
    "max_bytes_per_lane": {
      "default": 8388608,
      "maximum": 134217728,
      "minimum": 65536,
      "type": "integer"
    },
    "project": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "since": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix seconds; default one hour ago."
    },
    "terminal": {
      "anyOf": [
        {
          "maxLength": 256,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Substring of the source window title."
    },
    "text": {
      "anyOf": [
        {
          "maxLength": 512,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Terms matched against the event text."
    },
    "until": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Activity`; the full envelope schema is the `sinnix://gateway/v2/actions/activity.query` resource and `sinnix-agent-gateway catalog activity.query --schema`.

Examples:

Last hour of clipboard and notifications:

```json
{
  "kinds": [
    "clipboard",
    "notifications"
  ],
  "limit": 50
}
```

### `sessions.query`

List, read or search local coding-session JSONL files per provider.

Family: `query`. Owner: `sessions`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: claude sessions, codex sessions, transcript, session log.

Follow-up actions: `sessions.query`, `memory.query`, `timeline.query`.

Input schema:

```json
{
  "$defs": {
    "SessionsListOp": {
      "additionalProperties": false,
      "properties": {
        "limit": {
          "default": 100,
          "maximum": 500,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "list",
          "default": "list",
          "type": "string"
        },
        "provider": {
          "enum": [
            "claude-code",
            "codex"
          ],
          "type": "string"
        }
      },
      "required": [
        "provider"
      ],
      "type": "object"
    },
    "SessionsReadOp": {
      "additionalProperties": false,
      "properties": {
        "max_bytes": {
          "default": 64000,
          "maximum": 262144,
          "minimum": 1,
          "type": "integer"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "read",
          "default": "read",
          "type": "string"
        },
        "reference": {
          "description": "provider:relative/path.jsonl from a list or search row.",
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "reference"
      ],
      "type": "object"
    },
    "SessionsSearchOp": {
      "additionalProperties": false,
      "properties": {
        "max_results": {
          "default": 100,
          "maximum": 500,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "search",
          "default": "search",
          "type": "string"
        },
        "provider": {
          "enum": [
            "claude-code",
            "codex"
          ],
          "type": "string"
        },
        "query": {
          "maxLength": 1000,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "provider",
        "query"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "discriminator": {
        "mapping": {
          "list": "#/$defs/SessionsListOp",
          "read": "#/$defs/SessionsReadOp",
          "search": "#/$defs/SessionsSearchOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/SessionsListOp"
        },
        {
          "$ref": "#/$defs/SessionsReadOp"
        },
        {
          "$ref": "#/$defs/SessionsSearchOp"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "request"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.query` resource and `sinnix-agent-gateway catalog sessions.query --schema`.

Examples:

Recent Claude Code sessions:

```json
{
  "request": {
    "limit": 20,
    "operation": "list",
    "provider": "claude-code"
  }
}
```

Search:

```json
{
  "request": {
    "operation": "search",
    "provider": "codex",
    "query": "gateway"
  }
}
```

### `memory.query`

Search session-derived memory across providers or fetch one object by reference, with source provenance.

Family: `query`. Owner: `memory`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: remember, recall, what did we decide, semantic search.

Follow-up actions: `memory.query`, `sessions.query`.

Input schema:

```json
{
  "$defs": {
    "MemoryGetOp": {
      "additionalProperties": false,
      "properties": {
        "max_bytes": {
          "default": 64000,
          "maximum": 262144,
          "minimum": 1,
          "type": "integer"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "get",
          "default": "get",
          "type": "string"
        },
        "reference": {
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "reference"
      ],
      "type": "object"
    },
    "MemorySearchOp": {
      "additionalProperties": false,
      "properties": {
        "limit": {
          "default": 100,
          "maximum": 500,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "search",
          "default": "search",
          "type": "string"
        },
        "providers": {
          "anyOf": [
            {
              "items": {
                "enum": [
                  "claude-code",
                  "codex",
                  "polylogue",
                  "sinex",
                  "lynchpin"
                ],
                "type": "string"
              },
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "query": {
          "maxLength": 1000,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "query"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "discriminator": {
        "mapping": {
          "get": "#/$defs/MemoryGetOp",
          "search": "#/$defs/MemorySearchOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/MemorySearchOp"
        },
        {
          "$ref": "#/$defs/MemoryGetOp"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "required": [
    "request"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `MemoryResult`; the full envelope schema is the `sinnix://gateway/v2/actions/memory.query` resource and `sinnix-agent-gateway catalog memory.query --schema`.

Examples:

Search all sources:

```json
{
  "request": {
    "operation": "search",
    "query": "screenshot probe"
  }
}
```

### `timeline.query`

Session evidence ordered by file mtime within an RFC 3339 window, per provider, without claiming unavailable upstreams.

Family: `query`. Owner: `timeline`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: history, when did, sessions between, chronology.

Follow-up actions: `sessions.query`, `memory.query`, `activity.query`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "end": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "limit": {
      "default": 100,
      "maximum": 500,
      "minimum": 1,
      "type": "integer"
    },
    "providers": {
      "anyOf": [
        {
          "items": {
            "enum": [
              "claude-code",
              "codex",
              "polylogue",
              "sinex",
              "lynchpin"
            ],
            "type": "string"
          },
          "minItems": 1,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "query": {
      "anyOf": [
        {
          "maxLength": 1000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "start": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "RFC 3339 with timezone."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `TimelineResult`; the full envelope schema is the `sinnix://gateway/v2/actions/timeline.query` resource and `sinnix-agent-gateway catalog timeline.query --schema`.

Examples:

Yesterday's sessions:

```json
{
  "end": "2026-09-05T00:00:00Z",
  "start": "2026-09-04T00:00:00Z"
}
```

### `audit.verify`

Verify the tamper-evident audit hash chain end to end.

Family: `status`. Owner: `audit`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: audit chain, integrity, tamper check.

Follow-up actions: `audit.receipt`, `events.tail`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Verification`; the full envelope schema is the `sinnix://gateway/v2/actions/audit.verify` resource and `sinnix-agent-gateway catalog audit.verify --schema`.

Examples:

Verify:

```json
{}
```

### `audit.receipt`

Read one principal-scoped audit receipt by ref or id.

Family: `get`. Owner: `audit`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: receipt, what happened in that call.

Follow-up actions: `audit.verify`, `events.tail`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "receipt_id": {
      "anyOf": [
        {
          "maxLength": 36,
          "minLength": 36,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "ref": {
      "anyOf": [
        {
          "pattern": "^sinnix://receipts/[0-9a-fA-F-]{36}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Receipt`; the full envelope schema is the `sinnix://gateway/v2/actions/audit.receipt` resource and `sinnix-agent-gateway catalog audit.receipt --schema`.

Examples:

By ref:

```json
{
  "ref": "sinnix://receipts/00000000-0000-0000-0000-000000000000"
}
```

### `results.get`

Read one immutable stored response snapshot by ref or id.

Family: `get`. Owner: `results`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: result snapshot, replay response.

Follow-up actions: `audit.receipt`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "ref": {
      "anyOf": [
        {
          "pattern": "^sinnix://results/[^/]{1,128}$",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    },
    "result_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `ResultSnapshot`; the full envelope schema is the `sinnix://gateway/v2/actions/results.get` resource and `sinnix-agent-gateway catalog results.get --schema`.

Examples:

By id:

```json
{
  "result_id": "example-result"
}
```

### `capabilities.query`

Search the generated machine capability index or describe one capability exactly.

Family: `catalog`. Owner: `capability-index`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: what can this machine do, scripts, services, which command, capability index.

Follow-up actions: `capabilities.query`.

Input schema:

```json
{
  "$defs": {
    "DescribeOp": {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "name": {
          "maxLength": 1024,
          "minLength": 1,
          "type": "string"
        },
        "operation": {
          "const": "describe",
          "default": "describe",
          "type": "string"
        }
      },
      "required": [
        "name"
      ],
      "type": "object"
    },
    "SearchOp": {
      "additionalProperties": false,
      "properties": {
        "cursor": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "enabled": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kind": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "limit": {
          "default": 100,
          "maximum": 500,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "search",
          "default": "search",
          "type": "string"
        },
        "query": {
          "default": "",
          "description": "Terms matched against kind, name, description, invoke, owner and docs.",
          "maxLength": 1024,
          "type": "string"
        }
      },
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "actor": {
      "anyOf": [
        {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "deadline_at": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unix timestamp after which the call is refused."
    },
    "reason": {
      "anyOf": [
        {
          "maxLength": 2000,
          "minLength": 1,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "request": {
      "discriminator": {
        "mapping": {
          "describe": "#/$defs/DescribeOp",
          "search": "#/$defs/SearchOp"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/SearchOp"
        },
        {
          "$ref": "#/$defs/DescribeOp"
        }
      ]
    },
    "request_id": {
      "anyOf": [
        {
          "maxLength": 128,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Caller-chosen correlation id."
    }
  },
  "type": "object"
}
```

Output: the response envelope's `data` field is `Capabilities`; the full envelope schema is the `sinnix://gateway/v2/actions/capabilities.query` resource and `sinnix-agent-gateway catalog capabilities.query --schema`.

Examples:

Search:

```json
{
  "request": {
    "operation": "search",
    "query": "screenshot"
  }
}
```

Describe:

```json
{
  "request": {
    "name": "sinnix-observe",
    "operation": "describe"
  }
}
```
