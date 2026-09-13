<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v3-typed-actions -->
<!-- gateway-catalog-sha256: 19ccdfa0ccf89ac27206323b65535c2ab3e6940704a8795fb670a7d5c8f8c154 -->
# Sinnix Agent Gateway reference

Generated from `sinnix_agent_gateway.actions`. Every action is one MCP tool whose `tools/list` input schema is the one below; the catalog hash changes when any principal-visible action catalog row changes, including its schema, principal set, example or affordance.

Revision: `v3-typed-actions`. Catalog SHA-256: `19ccdfa0ccf89ac27206323b65535c2ab3e6940704a8795fb670a7d5c8f8c154`.

## Invocation

MCP: call the tool named after the action. CLI: `sinnix-agent-gateway call <action> --input '<json>'` or `--set key=value`; `sinnix-agent-gateway catalog <action> --schema` prints the live schemas.

## Resources

| Resource            | Owner              | Canonical reference                                      | Actions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------- | ------------------ | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project`           | `projects`         | `sinnix://projects/{project_id}`                         | `batches.list`, `batches.start`, `beads.batch.close`, `beads.blockers`, `beads.changeset`, `beads.claim`, `beads.claim_next`, `beads.close`, `beads.closure`, `beads.comment`, `beads.create`, `beads.cycles`, `beads.dependencies`, `beads.dependencies.add`, `beads.dependencies.count`, `beads.dependencies.remove`, `beads.graph`, `beads.graph.create`, `beads.memories`, `beads.memory.forget`, `beads.memory.get`, `beads.memory.remember`, `beads.metadata.compare_set`, `beads.operate`, `beads.query`, `beads.read`, `beads.related`, `beads.reopen`, `beads.unclaim`, `beads.update`, `campaign.progress`, `context.compose`, `events.tail`, `operations.run`, `projects.change`, `projects.context`, `projects.diff`, `projects.export`, `projects.get`, `projects.list`, `projects.read`, `projects.read_many`, `projects.search`, `projects.tree`, `shell.run` |
| `checkout`          | `projects`         | `sinnix://projects/{project_id}/checkouts/{checkout_id}` | `context.compose`, `operations.run`, `projects.change`, `projects.diff`, `projects.export`, `projects.get`, `projects.read`, `projects.read_many`, `projects.search`, `projects.tree`, `shell.run`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `bead`              | `beads`            | `sinnix://projects/{project_id}/beads/{bead_id}`         | `batches.start`, `batches.status`, `beads.batch.close`, `beads.blockers`, `beads.changeset`, `beads.claim`, `beads.claim_next`, `beads.close`, `beads.closure`, `beads.comment`, `beads.create`, `beads.cycles`, `beads.dependencies`, `beads.dependencies.add`, `beads.dependencies.count`, `beads.dependencies.remove`, `beads.get`, `beads.graph`, `beads.graph.create`, `beads.memories`, `beads.memory.forget`, `beads.memory.get`, `beads.memory.remember`, `beads.metadata.compare_set`, `beads.query`, `beads.read`, `beads.related`, `beads.reopen`, `beads.unclaim`, `beads.update`, `campaign.progress`, `wait.for`                                                                                                                                                                                                                                               |
| `task_authority`    | `beads`            | `sinnix://projects/{project_id}/task-authority`          | `beads.batch.close`, `beads.blockers`, `beads.changeset`, `beads.claim`, `beads.claim_next`, `beads.close`, `beads.closure`, `beads.comment`, `beads.create`, `beads.cycles`, `beads.dependencies`, `beads.dependencies.add`, `beads.dependencies.count`, `beads.dependencies.remove`, `beads.graph`, `beads.graph.create`, `beads.memories`, `beads.memory.forget`, `beads.memory.get`, `beads.memory.remember`, `beads.metadata.compare_set`, `beads.operate`, `beads.query`, `beads.read`, `beads.related`, `beads.reopen`, `beads.unclaim`, `beads.update`                                                                                                                                                                                                                                                                                                               |
| `run`               | `batches`          | `sinnix://projects/{project_id}/runs/{run_id}`           | `batches.land`, `batches.list`, `batches.resume`, `batches.start`, `batches.status`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `job`               | `jobs`             | `sinnix://jobs/{job_id}`                                 | `batches.land`, `batches.list`, `batches.resume`, `batches.start`, `batches.status`, `context.compose`, `events.tail`, `jobs.cancel`, `jobs.clean`, `jobs.get`, `jobs.list`, `jobs.logs`, `jobs.retry`, `jobs.wait`, `machine.operate`, `machine.prepare`, `operations.run`, `shell.run`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `artifact`          | `artifacts`        | `sinnix://artifacts/{artifact_id}`                       | `artifacts.get`, `artifacts.list`, `artifacts.read`, `browser.screenshot`, `desktop.screenshot`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `receipt`           | `audit`            | `sinnix://receipts/{receipt_id}`                         | `audit.receipt`, `audit.verify`, `events.tail`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `result`            | `results`          | `sinnix://results/{result_id}`                           | `results.get`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `machine_unit`      | `machine`          | `sinnix://machine/units/{manager}/{unit}`                | `machine.operate`, `machine.prepare`, `machine.query`, `machine.snapshot`, `machine.units.get`, `machine.units.list`, `machine.units.logs`, `machine.units.operate`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `browser_page`      | `browser`          | `sinnix://browser/pages/{page_id}`                       | `browser.operate`, `browser.page`, `browser.pages`, `browser.screenshot`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `browser_workspace` | `browser`          | `sinnix://browser/agent-workspace`                       | `browser.operate`, `browser.pages`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `process`           | `machine`          | `sinnix://processes/{pid}/{start_ticks}`                 | `machine.operate`, `machine.prepare`, `machine.query`, `processes.get`, `processes.list`, `processes.signal`, `processes.tree`, `processes.wait`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `terminal`          | `terminals`        | `sinnix://terminals/{terminal_id}`                       | `terminals.focus`, `terminals.get`, `terminals.list`, `terminals.open`, `terminals.processes`, `terminals.run`, `terminals.screen`, `terminals.scrollback`, `terminals.send`, `terminals.wait`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `desktop`           | `desktop`          | `sinnix://desktop/current`                               | `desktop.operate`, `desktop.screenshot`, `desktop.snapshot`, `desktop.tree`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `host_file`         | `files`            | `sinnix://files/{file_token}`                            | `files.change`, `files.changeset`, `files.list`, `files.patch`, `files.plan`, `files.read`, `files.references`, `files.search`, `files.stat`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `mcp_tool`          | `mcp-broker`       | `sinnix://mcp/{server}/tools/{tool}`                     | `mcp.call`, `mcp.change`, `mcp.servers`, `mcp.tools`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `capture_lane`      | `captures`         | `sinnix://captures/{lane}`                               | `activity.query`, `captures.query`, `wait.for`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `capability`        | `capability-index` | `sinnix://capabilities/{name}`                           | `capabilities.query`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `context_snapshot`  | `context`          | `sinnix://contexts/{snapshot_id}`                        | `context.compose`, `results.get`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

## Actions

| Action                       | Family    | Owner              | Principals                          | Summary                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------- | --------- | ------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `gateway.status`             | `status`  | `gateway`          | `agent-control, observer, operator` | Report the principal, contract hashes, tool count and per-route availability.                                                                                                                                                                                                                                                                    |
| `gateway.catalog`            | `catalog` | `gateway`          | `agent-control, observer, operator` | Every action is also an MCP tool with its full schema in tools/list; the catalog adds aliases, affordances, resource kinds and the brokered MCP tool inventory (lynchpin, sinex, polylogue).                                                                                                                                                     |
| `files.stat`                 | `query`   | `files`            | `observer, operator`                | Describe one host path: kind, size, mode, owner, timestamps, MIME, hash.                                                                                                                                                                                                                                                                         |
| `files.list`                 | `query`   | `files`            | `observer, operator`                | List a directory with a canonical ref for every child.                                                                                                                                                                                                                                                                                           |
| `files.read`                 | `query`   | `files`            | `observer, operator`                | Read a file: text inline, images as image blocks, other binary as read-only links.                                                                                                                                                                                                                                                               |
| `files.search`               | `query`   | `files`            | `observer, operator`                | Without content_regex the search is over paths (fd); with it, matching lines are returned (ripgrep --json). Results are bounded by limit and timeout.                                                                                                                                                                                            |
| `files.patch`                | `change`  | `files`            | `operator`                          | Pass expected_sha256 from the prior read so a concurrent change is refused instead of overwritten. Unified hunks are applied individually; rejected hunks are reported.                                                                                                                                                                          |
| `files.change`               | `change`  | `files`            | `operator`                          | Copy and move never overwrite an existing destination. Remove supports regular files only.                                                                                                                                                                                                                                                       |
| `files.plan`                 | `query`   | `organization`     | `operator`                          | The caller supplies every mapping. The plan hashes each regular source file and records collision, parent and filesystem facts without changing host files.                                                                                                                                                                                      |
| `files.changeset`            | `change`  | `organization`     | `operator`                          | All planned sources, destinations and parents are revalidated before the first mutation. Transfers never overwrite. Results are honest about partial completion and no global atomicity is claimed.                                                                                                                                              |
| `files.references`           | `query`   | `organization`     | `operator`                          | Runs the existing bounded files.search text primitive once for each supplied old path. It only reports provenance and never rewrites references.                                                                                                                                                                                                 |
| `projects.list`              | `query`   | `projects`         | `agent-control, observer, operator` | List the projects this principal may read, with canonical refs.                                                                                                                                                                                                                                                                                  |
| `projects.get`               | `get`     | `projects`         | `agent-control, observer, operator` | The checkout row carries head and dirty_sha256, the preconditions projects.change requires.                                                                                                                                                                                                                                                      |
| `projects.tree`              | `query`   | `projects`         | `agent-control, observer, operator` | List files under a project-relative directory without following symlinks.                                                                                                                                                                                                                                                                        |
| `projects.read`              | `query`   | `projects`         | `agent-control, observer, operator` | Read a bounded line range of one project file.                                                                                                                                                                                                                                                                                                   |
| `projects.read_many`         | `query`   | `projects`         | `agent-control, observer, operator` | Read several bounded project files from one checkout observation.                                                                                                                                                                                                                                                                                |
| `projects.export`            | `query`   | `projects`         | `agent-control, observer, operator` | Sensitive, local-only, hidden, and symlinked paths are excluded. The export is bounded and includes a manifest with file hashes and the checkout revision.                                                                                                                                                                                       |
| `projects.diff`              | `query`   | `projects`         | `agent-control, observer, operator` | Show uncommitted changes in a checkout, optionally against a git ref.                                                                                                                                                                                                                                                                            |
| `projects.search`            | `query`   | `projects`         | `agent-control, observer, operator` | Search project file contents with ripgrep.                                                                                                                                                                                                                                                                                                       |
| `projects.change`            | `change`  | `projects`         | `operator`                          | Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get, or expected_file_sha256 from projects.read.                                                                                                                            |
| `projects.context`           | `context` | `projects`         | `agent-control, observer, operator` | Components are budgeted independently; an unavailable component names its reason and source ref so the caller can follow the direct route.                                                                                                                                                                                                       |
| `beads.closure`              | `query`   | `beads`            | `agent-control, observer, operator` | Read native dependency closure, cycles, readiness and incomplete frontier at one revision.                                                                                                                                                                                                                                                       |
| `beads.query`                | `query`   | `beads`            | `agent-control, observer, operator` | The owner filters, projects and counts before serialization. limit sizes immutable observation pages; cursors never reread live rows. Owner coverage reports any bounded prefix; beads.read exposes native offset paging. at pins historical reads to an exact resolved Dolt revision. aggregate counts or groups without fetching issue bodies. |
| `beads.get`                  | `get`     | `beads`            | `agent-control, observer, operator` | Read one bead by ref, id or title fragment, with optional comments, history, dependencies or graph.                                                                                                                                                                                                                                              |
| `beads.operate`              | `operate` | `beads`            | `operator`                          | Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.                                                                                                                                                                                                                                              |
| `beads.read`                 | `query`   | `beads`            | `agent-control, observer, operator` | Read native Beads queries, counts or dependency closure with owner revisions and paging.                                                                                                                                                                                                                                                         |
| `beads.comment`              | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.dependencies.add`     | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.changeset`            | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.batch.close`          | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.graph.create`         | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.claim`                | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.claim_next`           | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.close`                | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.metadata.compare_set` | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.dependencies.count`   | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.create`               | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.memory.forget`        | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.graph`                | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.memory.get`           | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.blockers`             | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.dependencies`         | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.cycles`               | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.memories`             | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.related`              | `query`   | `beads`            | `agent-control, observer, operator` | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.unclaim`              | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.memory.remember`      | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.dependencies.remove`  | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.reopen`               | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `beads.update`               | `change`  | `beads`            | `operator`                          | The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.                           |
| `jobs.list`                  | `query`   | `systemd-jobs`     | `agent-control, observer, operator` | List queued jobs (pueue tasks) newest first, optionally for one project.                                                                                                                                                                                                                                                                         |
| `jobs.get`                   | `get`     | `systemd-jobs`     | `agent-control, observer, operator` | One job's state and bead binding, with its log range or typed result on request.                                                                                                                                                                                                                                                                 |
| `jobs.logs`                  | `get`     | `systemd-jobs`     | `agent-control, observer, operator` | A byte range of a job's bounded log (workload output, then the wrapper's stderr).                                                                                                                                                                                                                                                                |
| `jobs.wait`                  | `wait`    | `systemd-jobs`     | `agent-control, observer, operator` | The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job. A task id is a queue position: pass the launch_reference the start returned and the wait follows its job across a reorder, answering with the id it is at now.                                                                                |
| `jobs.cancel`                | `operate` | `systemd-jobs`     | `agent-control, operator`           | Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.                                                                                                                                                                                                                                        |
| `jobs.retry`                 | `operate` | `systemd-jobs`     | `agent-control, operator`           | Re-run a terminal job in place with the same launch input and id (pueue restart).                                                                                                                                                                                                                                                                |
| `jobs.clean`                 | `operate` | `systemd-jobs`     | `agent-control, operator`           | Refused while the job is still queued or running; cancel it first.                                                                                                                                                                                                                                                                               |
| `operations.run`             | `run`     | `systemd-jobs`     | `agent-control, operator`           | Queue one project-declared operation in its declared pool on the root or a worktree.                                                                                                                                                                                                                                                             |
| `shell.run`                  | `run`     | `systemd-jobs`     | `operator`                          | cwd is confined to the checkout. Default execution is asynchronous. wait=true waits up to wait_timeout_seconds (default 5, maximum 30) on the same job and returns bounded output; a timeout returns a continuation locator without cancelling the job.                                                                                          |
| `batches.list`               | `query`   | `systemd-jobs`     | `agent-control, observer, operator` | List batch runs newest first, with each worker's stage and task.                                                                                                                                                                                                                                                                                 |
| `batches.status`             | `get`     | `systemd-jobs`     | `agent-control, observer, operator` | Every id is a pueue task id: pass a worker's or the landing's job_id to jobs.logs, jobs.wait or jobs.cancel, with its job_launch_reference so the call survives a reorder.                                                                                                                                                                       |
| `batches.start`              | `run`     | `systemd-jobs`     | `agent-control, operator`           | backend, model and effort default to the project descriptor's packet defaults. Refused when a bead is claimed or already in a live run. The landing task is queued behind the workers and runs itself.                                                                                                                                           |
| `batches.land`               | `run`     | `systemd-jobs`     | `agent-control, operator`           | batches.start already queues the first landing behind the workers; this re-queues one after a landing failed. The landing runs as a job, so wait on landing_job_id rather than on this call.                                                                                                                                                     |
| `batches.resume`             | `run`     | `systemd-jobs`     | `agent-control, operator`           | backend, model and effort default to the worker's own. Refused while the worker's task is still queued or running.                                                                                                                                                                                                                               |
| `wait.for`                   | `wait`    | `waits`            | `agent-control, observer, operator` | Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token.                                                                                                                               |
| `events.tail`                | `events`  | `events`           | `agent-control, observer, operator` | Pass next_cursor back to continue; a cursor from another principal or project scope fails stale_cursor.                                                                                                                                                                                                                                          |
| `context.compose`            | `context` | `context`          | `agent-control, observer, operator` | The selected owner supplies domain composition, source coverage and partial results. The gateway preserves its product and availability in an immutable observation under snapshot_ref.                                                                                                                                                          |
| `desktop.snapshot`           | `status`  | `desktop`          | `observer, operator`                | One observation of the desktop: monitors, workspaces, focus, every window with geometry, and a generation stamp.                                                                                                                                                                                                                                 |
| `desktop.screenshot`         | `query`   | `desktop`          | `observer, operator`                | full captures the focused output through the HDR-aware screenshot owner; window/rect/monitor targets capture with grim. On HDR outputs a corrected SDR variant is produced and preferred for the image block.                                                                                                                                    |
| `desktop.tree`               | `query`   | `desktop`          | `observer, operator`                | Fails unavailable when the pyatspi bindings are absent from the gateway environment; Chromium apps expose a tree only when launched with accessibility forced on.                                                                                                                                                                                |
| `desktop.operate`            | `operate` | `desktop`          | `operator`                          | Pointer clicks, drags and scrolls need a virtual pointer tool (ydotool) on the host and fail unavailable without one; cursor moves always work. Window targets are natural locators; ambiguity returns candidates.                                                                                                                               |
| `terminals.list`             | `catalog` | `terminals`        | `observer, operator`                | Every kitty window with its ref, title, cwd, shell pid, focus and foreground processes.                                                                                                                                                                                                                                                          |
| `terminals.get`              | `get`     | `terminals`        | `observer, operator`                | Resolve one terminal by ref, kitty id, title, cwd, pid or focus.                                                                                                                                                                                                                                                                                 |
| `terminals.screen`           | `query`   | `terminals`        | `observer, operator`                | The visible screen text of one terminal.                                                                                                                                                                                                                                                                                                         |
| `terminals.scrollback`       | `query`   | `terminals`        | `observer, operator`                | The last N lines of a terminal's history, screen, or last command output.                                                                                                                                                                                                                                                                        |
| `terminals.processes`        | `query`   | `terminals`        | `observer, operator`                | Foreground processes of one terminal and whether its shell is at a prompt.                                                                                                                                                                                                                                                                       |
| `terminals.send`             | `operate` | `terminals`        | `operator`                          | Send text (optionally with Enter or bracketed paste) or key presses to one terminal.                                                                                                                                                                                                                                                             |
| `terminals.run`              | `run`     | `terminals`        | `operator`                          | Completion and output rely on kitty shell integration (at_prompt, last_cmd_output). exit_status is reported only with capture_exit_status, which appends a visible marker to the command line.                                                                                                                                                   |
| `terminals.wait`             | `wait`    | `terminals`        | `observer, operator`                | Wait until a terminal is at its prompt, shows a regex, finishes a process, or changes title.                                                                                                                                                                                                                                                     |
| `terminals.focus`            | `operate` | `terminals`        | `operator`                          | Focus one kitty window.                                                                                                                                                                                                                                                                                                                          |
| `terminals.open`             | `operate` | `terminals`        | `operator`                          | Open a new kitty window (OS window, split or tab) with an optional cwd and command; returns its ref.                                                                                                                                                                                                                                             |
| `browser.pages`              | `catalog` | `browser`          | `observer, operator`                | List every open Chrome page with its ref; flags the gateway-owned pages that can be read, captured or operated.                                                                                                                                                                                                                                  |
| `browser.page`               | `get`     | `browser`          | `observer, operator`                | Element refs (g<generation>e<n>) are attached to the DOM for this snapshot; a later snapshot or reload replaces them, and a stale ref fails not_found.                                                                                                                                                                                           |
| `browser.screenshot`         | `query`   | `browser`          | `observer, operator`                | Screenshot a gateway-owned page through CDP; the image rides in an image block and is retained as an artifact.                                                                                                                                                                                                                                   |
| `browser.operate`            | `operate` | `browser`          | `operator`                          | Operator tabs are never accepted as targets, even when a locator matches one. Element targets take a snapshot ref or a CSS selector.                                                                                                                                                                                                             |
| `machine.snapshot`           | `status`  | `machine`          | `agent-control, observer, operator` | Each section carries its own availability and source; GPU and network report unavailable because no owner exposes them.                                                                                                                                                                                                                          |
| `machine.query`              | `query`   | `machine`          | `agent-control, observer, operator` | Read one sinnix-observe section with cursor paging, or the ops-reducer revision (operation=actions).                                                                                                                                                                                                                                             |
| `machine.units.list`         | `query`   | `machine`          | `agent-control, observer, operator` | List systemd units of one manager with load/active/sub state and a canonical ref each.                                                                                                                                                                                                                                                           |
| `machine.units.get`          | `get`     | `machine`          | `agent-control, observer, operator` | Describe one unit via systemctl show: states, main pid, cgroup, restarts, timestamps.                                                                                                                                                                                                                                                            |
| `machine.units.logs`         | `query`   | `machine`          | `agent-control, observer, operator` | Journal entries for one unit (journalctl -o json), bounded by line count and bytes.                                                                                                                                                                                                                                                              |
| `machine.prepare`            | `get`     | `ops-reducer`      | `agent-control, observer, operator` | Read the selected target identity and action preconditions without changing it.                                                                                                                                                                                                                                                                  |
| `machine.operate`            | `operate` | `ops-reducer`      | `operator`                          | expected_target must match the target identity returned by machine.prepare; the reducer receipt is verified against the submitted action and target.                                                                                                                                                                                             |
| `machine.units.operate`      | `operate` | `ops-reducer`      | `operator`                          | Start, stop or restart one unit through the ops reducer (reload and wait are not reducer actions).                                                                                                                                                                                                                                               |
| `processes.list`             | `query`   | `machine`          | `agent-control, observer, operator` | List live processes filtered by name, pid, unit, cgroup or user, with a canonical ref each.                                                                                                                                                                                                                                                      |
| `processes.get`              | `get`     | `machine`          | `agent-control, observer, operator` | Describe one process: cmdline, cwd, exe, redacted env, cgroup/unit, parent, children, sockets, cpu and memory.                                                                                                                                                                                                                                   |
| `processes.tree`             | `query`   | `machine`          | `agent-control, observer, operator` | Parent/child process tree from one root or from every top-level process, bounded by depth and node count.                                                                                                                                                                                                                                        |
| `processes.signal`           | `operate` | `machine`          | `operator`                          | The reducer path is the attested one and needs expected_target; the direct path is receipted by the gateway audit chain only.                                                                                                                                                                                                                    |
| `processes.wait`             | `wait`    | `machine`          | `agent-control, observer, operator` | Wait until a process (same pid and start ticks) exits, or the bounded timeout elapses.                                                                                                                                                                                                                                                           |
| `mcp.servers`                | `status`  | `mcp-broker`       | `observer, operator`                | Each probe runs initialize + tools/list with a 5 s bound; a timeout stores the upstream stderr as an artifact and returns its ref.                                                                                                                                                                                                               |
| `mcp.tools`                  | `catalog` | `mcp-broker`       | `observer, operator`                | Catalog of every admitted upstream tool with its namespaced ref, input schema and read/change effect.                                                                                                                                                                                                                                            |
| `mcp.call`                   | `query`   | `mcp-broker`       | `observer, operator`                | Reads require an owner read-only annotation or an exact match to trusted registry selectors. Other requests require mcp.change (operator only). A target using server=sinnix-agent-gateway is routed to the named direct read action, preserving its native content blocks; changes stay direct-only.                                            |
| `mcp.change`                 | `change`  | `mcp-broker`       | `operator`                          | Invoke an upstream request not admitted as read-only by annotation or trusted registry selectors.                                                                                                                                                                                                                                                |
| `artifacts.list`             | `catalog` | `artifacts`        | `agent-control, observer, operator` | List principal-visible artifacts with kind, owner, size and canonical ref.                                                                                                                                                                                                                                                                       |
| `artifacts.get`              | `get`     | `artifacts`        | `agent-control, observer, operator` | Metadata of one artifact without its bytes.                                                                                                                                                                                                                                                                                                      |
| `artifacts.read`             | `query`   | `artifacts`        | `agent-control, observer, operator` | Read an artifact: text inline with offsets, images as image blocks, other binary as read-only links.                                                                                                                                                                                                                                             |
| `captures.query`             | `query`   | `captures`         | `agent-control, observer, operator` | List runtime-declared capture lanes, describe one, or read per-lane record deltas since a time.                                                                                                                                                                                                                                                  |
| `activity.query`             | `query`   | `captures`         | `agent-control, observer, operator` | Reads sinnix-capture-v1 envelope files under each lane path within the time window; coverage lists which lanes contributed and which have no envelope files.                                                                                                                                                                                     |
| `sessions.query`             | `query`   | `polylogue`        | `observer, operator`                | Read indexed session pages or explicit original-source fallback through Polylogue.                                                                                                                                                                                                                                                               |
| `memory.query`               | `query`   | `polylogue`        | `observer, operator`                | Search original session sources or read one source object with explicit coverage.                                                                                                                                                                                                                                                                |
| `timeline.query`             | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.list`              | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.search`            | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.read`              | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.raw.list`          | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.raw.search`        | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.raw.read`          | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.raw.timeline`      | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `memory.raw.get`             | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `memory.raw.search`          | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `sessions.resume`            | `query`   | `polylogue`        | `observer, operator`                | Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.                                                                                                                                                                                        |
| `campaign.progress`          | `query`   | `lynchpin`         | `observer, operator`                | Task closure, verified delivery and acceptance remain separate. Missing evidence is unknown; bounded closure cannot establish an exact denominator. Historical task state is read at its resolved owner revision.                                                                                                                                |
| `sessions.orchestration`     | `query`   | `polylogue`        | `observer, operator`                | Native parent, model and token fields remain unknown when absent from stored evidence. Each owner product retains its coverage, provenance and ingestion watermark.                                                                                                                                                                              |
| `audit.verify`               | `status`  | `audit`            | `agent-control, observer, operator` | Verify the tamper-evident audit hash chain end to end.                                                                                                                                                                                                                                                                                           |
| `audit.receipt`              | `get`     | `audit`            | `agent-control, observer, operator` | Read one principal-scoped audit receipt by ref or id.                                                                                                                                                                                                                                                                                            |
| `results.get`                | `get`     | `results`          | `agent-control, observer, operator` | Read one immutable stored response snapshot by ref or id.                                                                                                                                                                                                                                                                                        |
| `capabilities.query`         | `catalog` | `capability-index` | `agent-control, observer, operator` | Search the generated machine capability index or describe one capability exactly.                                                                                                                                                                                                                                                                |

### `gateway.status`

Report the principal, contract hashes, tool count and per-route availability.

Family: `status`. Owner: `gateway`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `catalog`. Owner: `gateway`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
    "max_hash_bytes": {
      "default": 268435456,
      "description": "Largest regular file hashed by this stat request; raise deliberately for larger files.",
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
      "$ref": "#/$defs/FileLocator"
    },
    "with_sha256": {
      "default": true,
      "description": "Hash a regular file within max_hash_bytes.",
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

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Read a file: text inline, images as image blocks, other binary as read-only links.

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Maximum inline text bytes.",
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
      "description": "auto returns text inline and binary files as canonical read-only links.",
      "enum": [
        "auto",
        "text"
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
    },
    "with_sha256": {
      "default": false,
      "description": "Compute a full-file SHA-256. Disabled by default for bounded reads.",
      "type": "boolean"
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

Family: `query`. Owner: `files`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `change`. Owner: `files`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `change`. Owner: `files`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

### `files.plan`

The caller supplies every mapping. The plan hashes each regular source file and records collision, parent and filesystem facts without changing host files.

Family: `query`. Owner: `organization`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: move plan, relocation preview.

Follow-up actions: `files.changeset`, `files.references`.

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
    "MoveMapping": {
      "additionalProperties": false,
      "properties": {
        "destination": {
          "$ref": "#/$defs/FileLocator"
        },
        "source": {
          "$ref": "#/$defs/FileLocator"
        }
      },
      "required": [
        "source",
        "destination"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "Only caller-selected moves and mkdirs are considered.",
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
    "mkdirs": {
      "items": {
        "$ref": "#/$defs/FileLocator"
      },
      "maxItems": 2000,
      "type": "array"
    },
    "moves": {
      "items": {
        "$ref": "#/$defs/MoveMapping"
      },
      "maxItems": 2000,
      "minItems": 1,
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
    }
  },
  "required": [
    "moves"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `PlanResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.plan` resource and `sinnix-agent-gateway catalog files.plan --schema`.

Examples:

Plan one explicit move:

```json
{
  "moves": [
    {
      "destination": {
        "path": "/realm/archive/a.txt"
      },
      "source": {
        "path": "/realm/tmp/work/a.txt"
      }
    }
  ]
}
```

### `files.changeset`

All planned sources, destinations and parents are revalidated before the first mutation. Transfers never overwrite. Results are honest about partial completion and no global atomicity is claimed.

Family: `change`. Owner: `organization`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: apply move plan, relocation changeset.

Follow-up actions: `files.stat`, `files.references`.

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
    "idempotency_key": {
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "plan_digest": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    },
    "plan_ref": {
      "pattern": "^sinnix://artifacts/[0-9a-fA-F-]{36}$",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "plan_ref",
    "plan_digest"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ChangesetResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.changeset` resource and `sinnix-agent-gateway catalog files.changeset --schema`.

Examples:

Apply an approved plan:

```json
{
  "idempotency_key": "apply-relocation-1",
  "plan_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "plan_ref": "sinnix://artifacts/00000000-0000-0000-0000-000000000000"
}
```

### `files.references`

Runs the existing bounded files.search text primitive once for each supplied old path. It only reports provenance and never rewrites references.

Family: `query`. Owner: `organization`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: find old paths, path references.

Follow-up actions: `files.read`, `files.plan`.

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
    "include_hidden": {
      "default": false,
      "type": "boolean"
    },
    "limit_per_path": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
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
    "old_paths": {
      "items": {
        "type": "string"
      },
      "maxItems": 64,
      "minItems": 1,
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
    "respect_ignore_files": {
      "default": true,
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
    "roots",
    "old_paths"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ReferencesResult`; the full envelope schema is the `sinnix://gateway/v2/actions/files.references` resource and `sinnix-agent-gateway catalog files.references --schema`.

Examples:

Find one old path:

```json
{
  "old_paths": [
    "/realm/data/old-note.md"
  ],
  "roots": [
    {
      "path": "/realm/project/sinnix"
    }
  ]
}
```

### `projects.list`

List the projects this principal may read, with canonical refs.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

### `projects.read_many`

Read several bounded project files from one checkout observation.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: bulk read, read files, batch files.

Follow-up actions: `projects.read`, `projects.change`, `projects.diff`.

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
    },
    "ReadRequest": {
      "additionalProperties": false,
      "properties": {
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
          "minimum": 1,
          "type": "integer"
        },
        "path": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "start_line": {
          "default": 1,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "path"
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
    "files": {
      "items": {
        "$ref": "#/$defs/ReadRequest"
      },
      "maxItems": 32,
      "minItems": 1,
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
      "$ref": "#/$defs/CheckoutLocator"
    }
  },
  "required": [
    "target",
    "files"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ReadMany`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.read_many` resource and `sinnix-agent-gateway catalog projects.read_many --schema`.

Examples:

Read two files:

```json
{
  "files": [
    {
      "end_line": 40,
      "path": "README.md"
    },
    {
      "end_line": 80,
      "path": "flake.nix"
    }
  ],
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.export`

Sensitive, local-only, hidden, and symlinked paths are excluded. The export is bounded and includes a manifest with file hashes and the checkout revision.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: snapshot, bundle, download project, portable export.

Follow-up actions: `projects.get`, `projects.read`.

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
    "max_bytes": {
      "default": 16777216,
      "maximum": 67108864,
      "minimum": 1,
      "type": "integer"
    },
    "max_files": {
      "default": 2000,
      "maximum": 10000,
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

Output: the response envelope's `data` field is `ProjectExport`; the full envelope schema is the `sinnix://gateway/v2/actions/projects.export` resource and `sinnix-agent-gateway catalog projects.export --schema`.

Examples:

Export a bounded checkout:

```json
{
  "max_bytes": 8000000,
  "max_files": 500,
  "target": {
    "project": "sinnix"
  }
}
```

### `projects.diff`

Show uncommitted changes in a checkout, optionally against a git ref.

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Paths stay project-relative and policy-excluded paths (.git, secrets, local-only agent state) are refused. Take expected_dirty_sha256 or expected_head from projects.get, or expected_file_sha256 from projects.read.

Family: `change`. Owner: `projects`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
    "expected_file_path": {
      "anyOf": [
        {
          "maxLength": 4096,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Project-relative file guarded by expected_file_sha256."
    },
    "expected_file_sha256": {
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
      "description": "SHA-256 returned by projects.read for the file being written."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `context`. Owner: `projects`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

### `beads.closure`

Read native dependency closure, cycles, readiness and incomplete frontier at one revision.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: dependency closure, campaign closure.

Follow-up actions: `beads.get`, `beads.query`, `campaign.progress`.

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
    "at": {
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
    "direction": {
      "default": "prerequisites",
      "enum": [
        "prerequisites",
        "dependents",
        "both"
      ],
      "type": "string"
    },
    "max_depth": {
      "default": 50,
      "maximum": 100,
      "minimum": 1,
      "type": "integer"
    },
    "max_nodes": {
      "default": 500,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "maxLength": 128,
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
    "relation": {
      "anyOf": [
        {
          "maxLength": 64,
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": "blocks"
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
    "roots": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "minItems": 1,
      "type": "array"
    }
  },
  "required": [
    "project",
    "roots"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ClosureOutput`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.closure` resource and `sinnix-agent-gateway catalog beads.closure --schema`.

Examples:

Blocking closure at a historical time:

```json
{
  "at": "2026-09-01T12:00:00Z",
  "max_nodes": 100,
  "project": "sinnix",
  "relation": "blocks",
  "roots": [
    "sinnix-abc1"
  ]
}
```

### `beads.query`

The owner filters, projects and counts before serialization. limit sizes immutable observation pages; cursors never reread live rows. Owner coverage reports any bounded prefix; beads.read exposes native offset paging. at pins historical reads to an exact resolved Dolt revision. aggregate counts or groups without fetching issue bodies.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: tasks, issues, todo, ready work, what is blocked, bd list, bd ready, backlog.

Follow-up actions: `beads.get`, `beads.update`, `projects.context`.

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
    "aggregate": {
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
      "description": "Count matching records; optional group_by status/type/priority/assignee/owner."
    },
    "at": {
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
      "description": "Exact revision or RFC3339 timestamp with timezone; all reads use the resolved revision."
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
      "description": "Native Beads comparison/AND/OR/NOT expression; parsing and time semantics belong to the owner."
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
      "description": "Page size within an immutable owner observation. Coverage reports any owner read bound; beads.read exposes native offset paging. Use aggregate for counts.",
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
          "additionalProperties": true,
          "type": "object"
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
    "projection": {
      "default": "summary",
      "enum": [
        "summary",
        "full"
      ],
      "type": "string"
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

Family: `get`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: show task, bd show, issue details, task notes.

Follow-up actions: `beads.update`, `beads.query`.

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
      "description": "Exact owner revision or RFC3339 timestamp with timezone, resolved to the latest reachable revision at or before it."
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

### `beads.operate`

Beads maintenance: publish the export snapshot, push or pull sync, create, list or restore backups.

Family: `operate`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

### `beads.read`

Read native Beads queries, counts or dependency closure with owner revisions and paging.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Aggregate": {
      "additionalProperties": false,
      "properties": {
        "group_by": {
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      },
      "type": "object"
    },
    "Order": {
      "additionalProperties": false,
      "properties": {
        "field": {
          "type": "string"
        },
        "reverse": {
          "type": "boolean"
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
    "aggregate": {
      "$ref": "#/$defs/Aggregate"
    },
    "at": {
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
    "depth": {
      "type": "integer"
    },
    "direction": {
      "type": "string"
    },
    "expression": {
      "type": "string"
    },
    "filters": {
      "additionalProperties": true,
      "type": "object"
    },
    "include": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "include_closed": {
      "type": "boolean"
    },
    "limit": {
      "type": "integer"
    },
    "max_edges": {
      "type": "integer"
    },
    "native_filters": {
      "additionalProperties": true,
      "type": "object"
    },
    "offset": {
      "type": "integer"
    },
    "order": {
      "$ref": "#/$defs/Order"
    },
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "projection": {
      "type": "string"
    },
    "provenance": {
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
    "relations": {
      "items": {
        "type": "string"
      },
      "type": "array"
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
    "roots": {
      "items": {
        "type": "string"
      },
      "type": "array"
    },
    "view": {
      "type": "string"
    }
  },
  "required": [
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.read` resource and `sinnix-agent-gateway catalog beads.read --schema`.

Examples:

Page a pinned dependency closure:

```json
{
  "at": "HEAD",
  "depth": 3,
  "direction": "dependencies",
  "limit": 50,
  "offset": 0,
  "project": {
    "project": "sinnix"
  },
  "relations": [
    "blocks"
  ],
  "roots": [
    "sinnix-abc1"
  ]
}
```

### `beads.comment`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "AddCommentRequest": {
      "additionalProperties": false,
      "description": "One comment to append. The issue is named by the path, so it is not a member here: a body carrying it too would give one request two spellings of one anchor and a question about what to do when they disagree.",
      "properties": {
        "author": {
          "description": "Who is signing the comment. CALLER-ASSERTED, and not the authenticated principal \u2014 see the operation description.\n\nTrimmed of surrounding space, then refused when the result is empty, when it exceeds 256 bytes or 255 characters (the storage column), or when it carries a control character. The bounds and the character rule are `actor`'s, unchanged, because the value lands in a column of the same width that every renderer of the thread prints, where an unfiltered C1 introducer is an escape-sequence payload.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "text": {
          "description": "The comment body, stored VERBATIM: newlines, surrounding space and unicode all survive, and nothing trims the value that lands in the row.\n\nNO LENGTH BOUND AND NO CHARACTER RULE, unlike `author` beside it, and both absences are the column: this one is `LONGTEXT` rather than a 255-character field, and a comment that is a stack trace or a diff is an ordinary comment. The only cap is the 1 MiB every body on this surface shares.\n\nBOTH PLANES AGREE ABOUT THAT, which is worth stating because they did not. `wisp_comments.text` was left `TEXT` \u2014 65535 bytes \u2014 when the durable column was widened, so a comment past that limit wrote fine against an issue and failed against a wisp, on an operation that resolves its anchor across both planes deliberately. A caller therefore could not know which side of the bound it was on until the write failed. The ephemeral column is widened to match, so this member's bound is one number rather than two.\n\nBlank after trimming is a `400` \u2014 a comment of nothing but whitespace carries no information and is almost always a shell quoting accident \u2014 and blankness is judged on a TRIMMED COPY while the stored value is untrimmed, so a comment that merely begins with a newline is a comment.",
          "type": "string"
        }
      },
      "required": [
        "author",
        "text"
      ],
      "type": "object"
    },
    "Path": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "body": {
      "$ref": "#/$defs/AddCommentRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.comment` resource and `sinnix-agent-gateway catalog beads.comment --schema`.

Examples:

Append one comment to an issue's thread:

```json
{
  "body": {
    "author": "example-worker",
    "text": "Focused regression checks passed."
  },
  "idempotency_key": "example-addComment-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.dependencies.add`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "AddDependenciesRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is asserting the edges, under `ClaimRequest.actor`'s rules and for the same reasons: the server trims it, refuses an empty result, anything longer than 256 BYTES, and any control character including newline. It is attributed on each `dependency_added` event a genuinely new edge records, and interpolated into the storage commit message.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "edges": {
          "description": "The edges to assert, in the caller's order. An empty array is a `400` rather than a successful no-op: a write request that writes nothing is a client bug, and answering it cheerfully is how a client whose own list filtered to nothing silently stops wiring anything.\n\nThe 100-edge cap is a bound on how long one request may hold a write transaction, not a statement about batch semantics. Split a larger graph; each request is atomic on its own \u2014 but note that splitting it changes what the cycle gate can see, since the gate runs over one request at a time.\n\nA per-edge refusal names its offender as `edges[i].member`.",
          "items": {
            "$ref": "#/$defs/DependencyEdge"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        }
      },
      "required": [
        "actor",
        "edges"
      ],
      "type": "object"
    },
    "DependencyEdge": {
      "additionalProperties": false,
      "description": "One directed edge, as a REQUEST names it. It is not `Dependency`, which is the stored row `GET /v0/beads/dependencies` returns and carries the columns storage assigned; this is the three members a caller supplies.",
      "properties": {
        "depends_on_id": {
          "description": "The edge's TARGET \u2014 the issue depended upon. An exact canonical id, an `external:` reference, or an id belonging to another repository. Only an absence this database can SEE is refused. It must differ from `issue_id`.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "issue_id": {
          "description": "The edge's SOURCE \u2014 the issue that depends on the other end. An EXACT canonical id, and one this database holds: an edge follows its source, so a source that names nothing is a `400`.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "description": "The edge type, from the same OPEN vocabulary `Dependency.type` carries: checked for being a storable value, never for membership of a known-types list, so a workspace's own type passes.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "depends_on_id",
        "issue_id",
        "type"
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
    "body": {
      "$ref": "#/$defs/AddDependenciesRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.dependencies.add` resource and `sinnix-agent-gateway catalog beads.dependencies.add --schema`.

Examples:

Assert dependency edges as one act:

```json
{
  "body": {
    "actor": "example-worker",
    "edges": [
      {
        "depends_on_id": "sinnix-abc1",
        "issue_id": "sinnix-abc2",
        "type": "blocks"
      }
    ]
  },
  "idempotency_key": "example-addDependencies-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.changeset`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "AddItem": {
      "maxLength": 255,
      "type": "string"
    },
    "ApplyBatchRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is applying the plan, under `ClaimRequest.actor`'s rules and for the same reasons: the server trims it, refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline.\n\nIt is attributed to every item and to the ONE history entry the request records, because a batch is one act by one caller.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "force_id_prefix": {
          "default": false,
          "description": "Permits an explicit `create.id` outside the workspace's configured issue prefix, for EVERY create item in the request. Without it such an id is refused by the role and arrives as a `400`.",
          "type": "boolean"
        },
        "items": {
          "description": "The items to apply, IN THE ORDER THEY ARE TO BE APPLIED. An empty array is a `400` rather than a successful no-op: a write request that writes nothing is a client bug, and answering it cheerfully is how a client whose own plan filtered to nothing silently stops writing.\n\nThe 100-item cap bounds how long one request may hold a write transaction, not batch semantics. Split a larger plan; each request is atomic on its own \u2014 but splitting it changes what the end gate can see, since the gate runs over one request at a time.\n\nA per-item refusal names its offender as `items[i].kind.member`.",
          "items": {
            "$ref": "#/$defs/ApplyItem"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        },
        "provenance": {
          "description": "Labels the version-control history entry this request records, under `updateIssue`'s rule: it changes how the entry READS, never whether one is recorded. Empty composes a default naming how many items of each kind landed and no ids.",
          "maxLength": 255,
          "type": "string"
        },
        "skip_per_edge_cycle_check": {
          "default": false,
          "description": "Drops the PER-EDGE cycle probe for a caller wiring a large graph, exactly as it does on `POST /v0/beads/dependencies:add`.\n\nIT NEVER DROPS THE END GATE, which runs once after every item and re-validates the whole graph this request built, and it never drops the self-dependency refusal. It trades per-edge attribution for speed, not validation for speed.",
          "type": "boolean"
        }
      },
      "required": [
        "actor",
        "items"
      ],
      "type": "object"
    },
    "ApplyCloseItem": {
      "additionalProperties": false,
      "description": "Closes one existing issue, under `POST /v0/beads/issues/{id}:close`'s rules including first-close-wins.",
      "properties": {
        "expected_version": {
          "description": "Requires the row's `revision` to equal this value, evaluated as-modified and checked before the idempotent close. A miss refuses the whole request with `409 precondition_failed`, and `ApplyUpdateItem.expected_version`'s already-written rule applies here identically.\n\nTHERE IS DELIBERATELY NO `expected_status` HERE. A close is idempotent \u2014 re-closing a closed issue is `changed: false` \u2014 so a guard spelled to refuse an already-closed row is asking for a REFUSAL where this verb answers with a no-op. That belongs on an `update` item whose `patch.status` crosses into the done category.\n\nDECODE IT AS A 64-BIT INTEGER, on `ApplyUpdateItem.expected_version`'s terms, including its note that a corrupted token here costs the whole plan.",
          "type": "integer"
        },
        "force": {
          "default": false,
          "description": "Bypasses close policy \u2014 the open-children refusal and the live-blocker refusal \u2014 and nothing else.\n\nCLOSE POLICY EVALUATES AT THIS ITEM, against the row as this request has already changed it. A LATER item that gives a closed parent an open child is NOT refused: the policy is a gate on the closing act, not an invariant the store maintains.",
          "type": "boolean"
        },
        "reason": {
          "description": "Why the issue is closed, stored and read back as `close_reason`. THE FIRST CLOSE WINS: an idempotent re-close writes neither this nor `session`.",
          "maxLength": 255,
          "type": "string"
        },
        "session": {
          "description": "The working session that closed the issue, stored and read back as `closed_by_session`, under the same first-close-wins rule.",
          "maxLength": 255,
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/Ref"
        }
      },
      "required": [
        "target"
      ],
      "type": "object"
    },
    "ApplyCreateItem": {
      "additionalProperties": false,
      "description": "Creates one issue and optionally NAMES it, so later items can reach the row without knowing an id the request has not minted yet.\n\nIt publishes the whole create vocabulary rather than `POST /v0/beads/issues:batchCreate`'s narrow one, and the additions are the point: `status`, `sender`, `metadata`, `ephemeral` and `no_history` are the members whose absence there makes that operation unusable for a caller composing a real plan.\n\nTHE EDGES ARE NOT HERE. An issue's dependencies and its parent are `dep_add` ITEMS, so the order of every edge in the request is total and there is exactly one spelling for an edge. An item carrying comments or dependencies on the issue is a `400`.\n\n`metadata` is the issue's own metadata document and must be a JSON OBJECT where it is present at all. It is stored as sent; the resolved ids `metadata_refs` splices are written over its top-level keys after every id in the request exists.",
      "properties": {
        "acceptance_criteria": {
          "type": "string"
        },
        "assignee": {
          "maxLength": 255,
          "type": "string"
        },
        "defer_until": {
          "description": "RFC 3339. The issue is hidden from ready work until then.",
          "format": "date-time",
          "type": "string"
        },
        "description": {
          "type": "string"
        },
        "design": {
          "type": "string"
        },
        "due_at": {
          "description": "RFC 3339.",
          "format": "date-time",
          "type": "string"
        },
        "ephemeral": {
          "default": false,
          "description": "Creates the issue on the EPHEMERAL plane rather than the durable one. Per item, exactly as it is for `POST /v0/beads/issues:batchCreate`, so one request may create durable issues and ephemeral ones together.\n\nThe two planes hold their edges in different tables, so a `dep_add` between two rows this request creates on OPPOSITE planes is refused with everything else the request asked for. Mutually exclusive with `no_history`.",
          "type": "boolean"
        },
        "estimated_minutes": {
          "description": "An estimate in minutes. Absent leaves it unset.",
          "type": "integer"
        },
        "external_ref": {
          "maxLength": 255,
          "type": "string"
        },
        "id": {
          "description": "An explicit id for the new row, CREATE-ONLY: an id that already names a stored row is a `409` `already_exists` and the whole request is refused \u2014 never an adoption and never an overwrite. To act on a row that already exists, send an `update` item referencing it by `{\"id\": \u2026}`. The id is checked against the workspace's configured issue prefix unless the request sets `force_id_prefix`.\n\nAbsent is the ordinary case and the server mints one. This is the member `POST /v0/beads/issues:batchCreate` deliberately does not publish, which is why that operation can never adopt or overwrite a stored row and this one can be refused for trying.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "issue_type": {
          "description": "Issue type. Spelled `issue_type` rather than `type`, matching the member `Issue` carries, and validated against the built-ins plus the workspace's configured custom types by the ROLE \u2014 this server cannot read that vocabulary without a transaction, so it checks only what this schema declares and an unknown one arrives as a `400`.",
          "maxLength": 255,
          "type": "string"
        },
        "key": {
          "description": "This item's name inside the request. OPTIONAL \u2014 an item nothing refers to needs no name \u2014 and unique across the request's create items; a repeat is a `400`. It is what a later `Ref.key` resolves to, and the response's `keys` member is where the id it was bound to is read.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "labels": {
          "description": "The complete label set the issue is created with. Authoritative, not a patch \u2014 a create has nothing to add to.",
          "items": {
            "$ref": "#/$defs/Label"
          },
          "type": "array"
        },
        "metadata": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "metadata_refs": {
          "additionalProperties": {
            "$ref": "#/$defs/Ref"
          },
          "description": "Splices resolved ids into this issue's metadata: each entry writes the id its `Ref` resolves to as the WHOLE VALUE of one top-level metadata key.\n\nIT IS THE ONE PLACE A KEY MAY REACH FORWARD, or name this item's own `key` \u2014 see the operation's description. A ref here that names a key NO item declares is still a `400`.\n\nIT IS A TYPED MAP, NOT TEMPLATING. A `${key}` placeholder inside a JSON string would have no escape for a literal dollar-brace, would collide with every other templating language a caller's own values might carry, and could not be type-checked at all. This is one key, one whole value, one level deep.\n\nThe splice is applied AFTER the row is created, so a consumer of the event stream sees a create and then an update on the spliced row.",
          "type": "object"
        },
        "no_history": {
          "default": false,
          "description": "Creates the issue on the ephemeral plane WITHOUT history, and without the garbage collection an ordinary ephemeral row is eligible for. Mutually exclusive with `ephemeral`.",
          "type": "boolean"
        },
        "notes": {
          "type": "string"
        },
        "owner": {
          "description": "The human owner, which is a different member from `assignee`: the assignee is who is working it now, the owner is who it is attributed to.",
          "maxLength": 255,
          "type": "string"
        },
        "priority": {
          "description": "0 is P0/critical. Absent means the workspace default.",
          "maximum": 4,
          "minimum": 0,
          "type": "integer"
        },
        "sender": {
          "description": "Who sent this, for the message-shaped rows a plan creates. Stored verbatim and interpreted by nothing on this surface.",
          "maxLength": 255,
          "type": "string"
        },
        "status": {
          "description": "The status the issue is created in, from this workspace's own configured vocabulary. Absent means the workspace default.",
          "maxLength": 255,
          "type": "string"
        },
        "title": {
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "title"
      ],
      "type": "object"
    },
    "ApplyDepAddItem": {
      "additionalProperties": false,
      "description": "Asserts ONE dependency edge, under `POST /v0/beads/dependencies:add`'s rules. An edge from a row to itself is a `400`.\n\nA TARGET NEED NOT BE A ROW THIS DATABASE HOLDS: an `external:` reference and an id belonging to another repository are legitimate targets, so only an absence this database can SEE is refused. A SOURCE has no such latitude \u2014 an edge follows its source, so a source this database holds no row for has no plane to land in.\n\n`metadata` is the edge's type-specific JSON blob, and an OBJECT where it is present at all. Most edge types carry none.\n\nA WAITS-FOR EDGE IS NORMALIZED RATHER THAN STORED AS ASKED. An absent, empty or `{}` `metadata` on a `waits-for` edge is STORED as `{\"gate\":\"all-children\"}`, because a stored waits-for row must be self-describing: readers predating the gate's introduction do not default a missing one, so an empty gate is a row those readers get wrong. A metadata that names a gate keeps it, along with the spawner and also-blocks members a caller may carry, and a gate that is neither `all-children` nor `any-children` is a `400`. Nothing else about that member is interpreted.\n\nTHERE IS NO TYPED `waits_for` MEMBER, and that is the shape rather than an omission: every measured caller already carries the gate as metadata, a typed spelling lowers to these same bytes, and the blob carries members a two-field typed member could not express. One spelling, and it is this one.",
      "properties": {
        "metadata": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "source": {
          "$ref": "#/$defs/Ref"
        },
        "target": {
          "$ref": "#/$defs/Ref"
        },
        "type": {
          "description": "The edge type, from the same OPEN vocabulary `Dependency.type` carries: checked for BEING a storable value, never for membership of a known-types list, so a workspace's own type passes.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "source",
        "target",
        "type"
      ],
      "type": "object"
    },
    "ApplyItem": {
      "additionalProperties": false,
      "description": "One item of a plan: a `kind` naming what it does, plus exactly one payload member matching it.\n\nIT IS A TAGGED SINGLE-SHAPE OBJECT rather than a polymorphic one, and the spelling is deliberate. This document uses no `oneOf`, `anyOf` or `allOf` anywhere: a component carrying a composition keyword alongside the `x-go-type` pins the response schemas depend on silently loses the pin, and the generated result is a second wire struct that drifts from the canonical one. So the union is carried as four OPTIONAL members with a required tag rather than as a schema alternation.\n\nWHAT A CLIENT MUST DO, since no validator can enforce it from this schema alone: send `kind`, send the ONE member `kind` names, and send no other. An item carrying no payload does nothing; an item carrying a payload its `kind` does not name has two halves that disagree; an item carrying two payloads cannot say which it meant. All three are a `400` and nothing in the request is written. A generated client's type will make all four members constructible at once \u2014 that is the cost of the spelling, and checking it is the client's.\n\nREADING one is the same rule from the other side: dispatch on `kind` and read only that member. The other three are absent.",
      "properties": {
        "close": {
          "$ref": "#/$defs/ApplyCloseItem"
        },
        "create": {
          "$ref": "#/$defs/ApplyCreateItem"
        },
        "dep_add": {
          "$ref": "#/$defs/ApplyDepAddItem"
        },
        "kind": {
          "description": "Which member below is read. A CLOSED set, unlike a dependency `type`: every value here is a verb this operation implements, and an unknown one is a request the server cannot execute rather than a workspace's own vocabulary.",
          "enum": [
            "create",
            "update",
            "close",
            "dep_add"
          ],
          "type": "string"
        },
        "update": {
          "$ref": "#/$defs/ApplyUpdateItem"
        }
      },
      "required": [
        "kind"
      ],
      "type": "object"
    },
    "ApplyLabelPatch": {
      "additionalProperties": false,
      "description": "An ordered label edit: `replace` first, then `add`, then `remove`, so REMOVAL WINS when the same label appears in more than one member.\n\nIt is the full patch rather than `IssuePatchBody.labels`' complete replacement because a plan edits a set it did not compose: replacing would mean reading the labels back first, and the read this operation exists to avoid is exactly that one.\n\nRepetition is free in both directions \u2014 a label named twice in one member is applied once, and removing a label the issue does not carry is a no-op. An EMPTY-STRING entry is dropped rather than refused: a label row holding \"\" renders as nothing and matches nothing, so refusing the whole request for one stray entry would fail an otherwise-good edit.",
      "properties": {
        "add": {
          "description": "Labels to add after any replacement.",
          "items": {
            "$ref": "#/$defs/AddItem"
          },
          "type": "array"
        },
        "remove": {
          "description": "Labels to remove after replacement and addition.",
          "items": {
            "$ref": "#/$defs/RemoveItem"
          },
          "type": "array"
        },
        "replace": {
          "description": "The complete starting label set. An empty array CLEARS every label; omitting the member leaves the current set as the starting point.",
          "items": {
            "$ref": "#/$defs/ReplaceItem"
          },
          "type": "array"
        }
      },
      "type": "object"
    },
    "ApplyMetadataPatch": {
      "additionalProperties": false,
      "description": "A metadata edit. `replace` is mutually exclusive with the other three; without it the edits apply as `merge`, then `set` in key order, then `unset`, so UNSETTING A KEY WINS over setting or merging it. Sending `replace` beside any of the others is a `400`.\n\n`replace` replaces the whole document. Present holding `null`, `{}` or an empty value CLEARS metadata \u2014 and clearing STORES THE EMPTY JSON DOCUMENT rather than SQL null, so \"created with no metadata\" and \"given metadata and then cleared\" are the same stored value; a reader must treat absent, empty and `{}` as one value on the way out. `merge` must be a nonempty JSON OBJECT and is merged into the current document.",
      "properties": {
        "merge": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "replace": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "set": {
          "additionalProperties": {
            "anyOf": [
              {
                "$ref": "#/$defs/MetadataValue"
              },
              {
                "type": "null"
              }
            ]
          },
          "description": "Individual top-level keys to write, in deterministic key order. A value present holding `null` writes JSON null; a key is removed with `unset`, never by sending a null here.",
          "type": "object"
        },
        "unset": {
          "description": "Top-level keys to remove, applied after every other edit.",
          "items": {
            "$ref": "#/$defs/UnsetItem"
          },
          "type": "array"
        }
      },
      "type": "object"
    },
    "ApplyPatchBody": {
      "additionalProperties": false,
      "description": "The fields an `update` item writes. Every member is optional and PRESENCE is the signal: a member present is written, a member absent is untouched. An empty object is a `400` \u2014 a write that writes nothing is a client bug.\n\nIt mirrors `IssuePatchBody` member for member and diverges in exactly two places now that `PATCH /v0/beads/issues/{id}` publishes `status`, `assignee` and the same `metadata` algebra.\n\n`owner` is published here and not there, which is an accident of order rather than a decision: nothing has asked for it on the single patch.\n\n`labels` is a full patch rather than a complete replacement, and that one is a real difference: a plan has to be able to REMOVE one label without knowing the rest of the set, because it edits a set it did not compose. A caller patching one row it just read already knows the set.\n\n`parent_id` is deliberately absent, and its absence is this operation's one-edge-one-spelling rule: a parent is a `dep_add` item of type `parent-child`, so the order of every edge in the request stays total. The single patch has no ordering to express and publishes it directly. `persistence` is absent from both \u2014 moving a row between planes mid-plan is a different act from writing its fields, and nothing has asked for it here.",
      "properties": {
        "acceptance_criteria": {
          "type": "string"
        },
        "append_notes": {
          "description": "Appends to the notes rather than replacing them. Mutually exclusive with `notes`.",
          "type": "string"
        },
        "assignee": {
          "description": "The assignee. A transfer away from a live foreign in-progress owner is refused with `409 already_claimed` unless `force_assignee_transfer` is set or `expected_assignee` matched.",
          "maxLength": 255,
          "type": "string"
        },
        "defer_until": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "RFC 3339. Explicit `null` CLEARS the deferral."
        },
        "description": {
          "type": "string"
        },
        "design": {
          "type": "string"
        },
        "due_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "RFC 3339. Explicit `null` CLEARS the due date."
        },
        "estimated_minutes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "description": "Explicit `null` CLEARS the estimate."
        },
        "external_ref": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "Explicit `null` CLEARS the reference."
        },
        "issue_type": {
          "description": "The issue type, from this workspace's own configured vocabulary. A type outside it is refused by the ROLE and reaches the client as a `400`.",
          "maxLength": 255,
          "type": "string"
        },
        "labels": {
          "$ref": "#/$defs/ApplyLabelPatch"
        },
        "metadata": {
          "$ref": "#/$defs/ApplyMetadataPatch"
        },
        "notes": {
          "description": "Replaces the notes. Mutually exclusive with `append_notes`; sending both is a `400`.",
          "type": "string"
        },
        "owner": {
          "maxLength": 255,
          "type": "string"
        },
        "priority": {
          "maximum": 4,
          "minimum": 0,
          "type": "integer"
        },
        "status": {
          "description": "The issue's status, from this workspace's own configured vocabulary.\n\nA STATUS THAT CROSSES INTO THE DONE CATEGORY ANSWERS TO CLOSE POLICY: the item is refused with `409 not_closable` for open children or a live blocker unless `force_close_policy` is set. A done-to-done change and a move OUT of the done category are unaffected \u2014 which is how a plan reopens a row, since there is no reopen item.",
          "maxLength": 255,
          "type": "string"
        },
        "title": {
          "description": "Must not be blank after trimming; the length bound is what the column holds.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "type": "object"
    },
    "ApplyUpdateItem": {
      "additionalProperties": false,
      "description": "Patches one existing issue, under `PATCH /v0/beads/issues/{id}`'s rules.\n\nThe two carry the same preconditions and the same force flags; what is this operation's alone is that its guards evaluate AS-MODIFIED \u2014 against the row as earlier items of this same request have already changed it \u2014 and that a miss takes the whole plan down rather than one write.",
      "properties": {
        "expected_assignee": {
          "description": "Requires the issue's assignee to equal this value, evaluated as-modified. A match AUTHORIZES the requested `patch.assignee` transfer: this compare-and-set replaces the ordinary anti-steal fence, so it must not be combined with `force_assignee_transfer`. A miss refuses the whole request with `409 precondition_failed`.",
          "maxLength": 255,
          "type": "string"
        },
        "expected_status": {
          "description": "Requires the issue's status to equal this value, evaluated AS-MODIFIED \u2014 against the row as this request has already changed it at this item's position. A miss refuses the whole request with `409 precondition_failed`.",
          "maxLength": 255,
          "type": "string"
        },
        "expected_version": {
          "description": "Requires the row's `revision` to equal this value before the patch. A miss refuses the WHOLE request with `409 precondition_failed`.\n\nIT IS A `400`, NOT A `409`, ON A ROW THIS REQUEST HAS ALREADY WRITTEN \u2014 including one an earlier item created. The token is minted by the write, so mid-request there is no value a caller could send: the pre-request token is stale by construction and a row this request just created never had one the caller could read. Refusing statically says so; answering with a mismatch would send the caller looking for a concurrent writer that does not exist.\n\n`expected_status` and `expected_assignee` carry no such rule, because a caller CAN know what its own earlier item set them to.\n\nDECODE IT AS A 64-BIT INTEGER, for the reason `UpdateIssueRequest.expected_version` spells out. It bites harder here than anywhere else on the surface: a corrupted token refuses the WHOLE plan rather than one write, so a client with a lossy parser loses every item of every batch it guards.",
          "type": "integer"
        },
        "force_assignee_transfer": {
          "default": false,
          "description": "Bypasses ONLY a genuine transfer away from a live foreign in-progress owner. Reasserting the exact current assignee is idempotent and needs no force. It requires `patch.assignee` \u2014 a request setting it without one is a `400` \u2014 and it must be false when `expected_assignee` is sent.",
          "type": "boolean"
        },
        "force_close_policy": {
          "default": false,
          "description": "Bypasses ONLY close policy \u2014 the open-children refusal and the live blocker refusal \u2014 for a `patch.status` that crosses into the workspace's done category. It has no effect without such a status change, and it never bypasses validation, the preconditions above, or the assignee fence.",
          "type": "boolean"
        },
        "patch": {
          "$ref": "#/$defs/ApplyPatchBody"
        },
        "target": {
          "$ref": "#/$defs/Ref"
        }
      },
      "required": [
        "patch",
        "target"
      ],
      "type": "object"
    },
    "Label": {
      "maxLength": 255,
      "type": "string"
    },
    "MetadataValue": {
      "anyOf": [
        {},
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "One metadata value: ANY JSON value \u2014 string, number, boolean, null, array or object \u2014 because typed values enter through the explicit JSON metadata path and persist in older rows. It is not a string, and a client must not decode it as one.\n\nWhere a member of this type is OMITTED, the key is absent; where it is present holding `null`, the key exists and holds null. Those are different states and this surface reports both."
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
    "Ref": {
      "additionalProperties": false,
      "description": "Names ONE issue, either by an id that already exists or by the `key` a create item earlier in the same request gave itself.\n\nEXACTLY ONE OF THE TWO IS SET, and both cases the schema cannot express are a `400`: both members set is a caller that cannot say which it meant, and neither set is a reference to nothing. (Spelling that as a schema alternation would need `oneOf`, which this document does not use \u2014 see `ApplyItem`.)\n\nA KEY REACHES BACKWARD ONLY where the ref ADDRESSES a row \u2014 an `update.target`, a `close.target`, either endpoint of a `dep_add`. The one exception is `create.metadata_refs`, whose values may reach forward or name their own item's key; the operation's description says why.",
      "properties": {
        "id": {
          "description": "An id that already exists, EXACTLY. There is no fuzzy, prefix or cross-repo resolution on this surface.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "key": {
          "description": "The `key` a create item in THIS REQUEST gave itself. It is not an id, it is not stored anywhere, and it is resolved to the id the request minted \u2014 which the response's `keys` member reports.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "type": "object"
    },
    "RemoveItem": {
      "maxLength": 255,
      "type": "string"
    },
    "ReplaceItem": {
      "maxLength": 255,
      "type": "string"
    },
    "UnsetItem": {
      "maxLength": 255,
      "type": "string"
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
    "body": {
      "$ref": "#/$defs/ApplyBatchRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.changeset` resource and `sinnix-agent-gateway catalog beads.changeset --schema`.

Examples:

Apply an ordered, heterogeneous plan as one act:

```json
{
  "body": {
    "actor": "example-worker",
    "items": [
      {
        "create": {
          "key": "implementation",
          "title": "Implement bounded result paging"
        },
        "kind": "create"
      },
      {
        "create": {
          "key": "verification",
          "title": "Verify result paging"
        },
        "kind": "create"
      },
      {
        "dep_add": {
          "source": {
            "key": "verification"
          },
          "target": {
            "key": "implementation"
          },
          "type": "blocks"
        },
        "kind": "dep_add"
      }
    ]
  },
  "idempotency_key": "example-applyBatch-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.batch.close`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "BatchCloseItem": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id, resolved across BOTH planes. No fuzzy, prefix or substring resolution \u2014 `IssueID`'s rule.\n\nA DUPLICATE is admissible; see the operation description.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "reason": {
          "description": "Why THIS issue is closed. It is per item rather than per request because `bd close a b c --reason x --reason y --reason z` has always mapped them positionally, and one request-wide reason could not express it. `CloseIssueRequest.reason`'s rules and first-close-wins.",
          "maxLength": 255,
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "type": "object"
    },
    "BatchCloseRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is closing. `ClaimRequest.actor`'s rules exactly, and the value is recorded against every item.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "force": {
          "default": false,
          "description": "Bypass close policy \u2014 the open-children refusal and the live-blocker refusal \u2014 for EVERY item, and nothing else. It never bypasses validation and it never bypasses existence: an id that names nothing refuses whether or not this is set. It is request-wide because the flag that spells it is.",
          "type": "boolean"
        },
        "items": {
          "description": "The issues to close, in the order the caller asked for them. Every item appears in `outcomes` at the same index.\n\nAn EMPTY array is a `400` rather than an empty answer, and the cap is `batchCreateIssues`' cap for its reason: it bounds how long one request may hold a write transaction.",
          "items": {
            "$ref": "#/$defs/BatchCloseItem"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        },
        "session": {
          "description": "The working session, recorded against every item that closes, under `CloseIssueRequest.session`'s first-close-wins rule and bounds.",
          "maxLength": 255,
          "type": "string"
        }
      },
      "required": [
        "actor",
        "items"
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
    "body": {
      "$ref": "#/$defs/BatchCloseRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.batch.close` resource and `sinnix-agent-gateway catalog beads.batch.close --schema`.

Examples:

Close many issues as one act:

```json
{
  "body": {
    "actor": "example-worker",
    "items": [
      {
        "id": "sinnix-abc1",
        "reason": "Acceptance checks passed"
      }
    ]
  },
  "idempotency_key": "example-batchCloseIssues-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.graph.create`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "BatchCreateDependency": {
      "additionalProperties": false,
      "properties": {
        "target_id": {
          "description": "The far end of the edge: an issue this workspace holds, an `external:` reference, or an id whose prefix belongs to another repository. Anything else is a `400` and nothing is created.\n\nNOT AN ITEM OF THIS REQUEST. The server assigns every id and an item carries no name, so there is nothing here a caller could write to address one; see the operation's description for the operation that can.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "description": "The edge type, from the same OPEN vocabulary `Dependency.type` carries. It is spelled `type` because that is the member an edge carries everywhere else on this surface.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "target_id",
        "type"
      ],
      "type": "object"
    },
    "BatchCreateItem": {
      "additionalProperties": false,
      "properties": {
        "acceptance_criteria": {
          "type": "string"
        },
        "assignee": {
          "maxLength": 255,
          "type": "string"
        },
        "dependencies": {
          "description": "The edges this issue is created carrying. They are written in the same transaction as the issue, so this operation never publishes an issue whose declared relationships are not there yet.",
          "items": {
            "$ref": "#/$defs/BatchCreateDependency"
          },
          "maxItems": 100,
          "type": "array"
        },
        "description": {
          "type": "string"
        },
        "design": {
          "type": "string"
        },
        "issue_type": {
          "description": "Issue type. Spelled `issue_type` rather than `type`, matching the member `Issue` carries, and validated against the built-ins plus the workspace's configured custom types \u2014 an unknown one is a `400`.",
          "type": "string"
        },
        "labels": {
          "items": {
            "$ref": "#/$defs/Label"
          },
          "type": "array"
        },
        "priority": {
          "description": "0 is P0/critical. Absent means the workspace default.",
          "maximum": 4,
          "minimum": 0,
          "type": "integer"
        },
        "title": {
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "title"
      ],
      "type": "object"
    },
    "BatchCreateRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is creating the issues, under `ClaimRequest.actor`'s rules and for the same reasons: the server trims it, refuses an empty result, anything longer than 256 BYTES, and any control character including newline. It is attributed to every item and interpolated into the storage commit message.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "items": {
          "description": "The issues to create, in order. An empty array is a `400` rather than a successful no-op: a write request that writes nothing is a client bug, and answering it with a cheerful empty success is how a client whose own list filtered to nothing silently stops creating anything.\n\nThe 100-item cap is a bound on how long one request may hold a write transaction, not a statement about batch semantics. Split a larger plan; each request is atomic on its own.",
          "items": {
            "$ref": "#/$defs/BatchCreateItem"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        }
      },
      "required": [
        "actor",
        "items"
      ],
      "type": "object"
    },
    "Label": {
      "maxLength": 255,
      "type": "string"
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
    "body": {
      "$ref": "#/$defs/BatchCreateRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.graph.create` resource and `sinnix-agent-gateway catalog beads.graph.create --schema`.

Examples:

Create many issues as one act:

```json
{
  "body": {
    "actor": "example-worker",
    "items": [
      {
        "title": "Add a bounded reader"
      },
      {
        "title": "Document reader pagination"
      }
    ]
  },
  "idempotency_key": "example-batchCreateIssues-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.claim`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "ClaimRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is claiming the issue. The server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline: Unicode category Cc \u2014 C0, DEL and the C1 block \u2014 plus the U+2028/U+2029 line separators, which is the set the `pattern` above spells.\n\nThe value is persisted as the assignee and interpolated into the storage commit message, so an unvalidated newline would forge audit-trail lines. C1 is refused for that same reason and not for tidiness: U+0085 is a line break on a VT-conformant terminal, and U+009B is the one-byte CSI introducer, which would make an actor an escape-sequence payload in anything that prints an assignee.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        }
      },
      "required": [
        "actor"
      ],
      "type": "object"
    },
    "Path": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "body": {
      "$ref": "#/$defs/ClaimRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.claim` resource and `sinnix-agent-gateway catalog beads.claim --schema`.

Examples:

Claim an issue for an actor:

```json
{
  "body": {
    "actor": "example-worker"
  },
  "idempotency_key": "example-claimIssue-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.claim_next`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "ClaimNextRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is claiming. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value is persisted as the assignee and interpolated into the storage commit message, so an unvalidated newline would forge audit-trail lines.\n\nIT IS THE ONLY BODY MEMBER, and the FILTER travels in the query string instead. That split is deliberate: the filter vocabulary is `GET /v0/beads/ready`'s and is decoded by the same function, so re-spelling it as a body object would create a second expression of one predicate \u2014 and two spellings of one predicate eventually disagree. The actor cannot go the same way: it is provenance that lands in a column, and this surface has always carried that in a body.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        }
      },
      "required": [
        "actor"
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
    "Query": {
      "additionalProperties": false,
      "properties": {
        "assignee": {
          "description": "Only issues assigned to this actor.",
          "type": "string"
        },
        "exclude_label": {
          "description": "Labels that must not be present.",
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "exclude_type": {
          "description": "Issue types to exclude. Repeat the parameter, or pass a comma-separated list. Ignored when `type` is set.",
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "has_metadata_key": {
          "description": "Only issues carrying this top-level metadata key.",
          "type": "string"
        },
        "include_deferred": {
          "default": false,
          "description": "Include issues whose `defer_until` is still in the future.",
          "type": "boolean"
        },
        "include_ephemeral": {
          "default": false,
          "description": "Include ephemeral (non-synced) rows.",
          "type": "boolean"
        },
        "label": {
          "description": "Labels that must ALL be present (AND).",
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "label_any": {
          "description": "Labels of which at least one must be present (OR).",
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "label_pattern": {
          "description": "Glob matched against labels.",
          "type": "string"
        },
        "label_regex": {
          "description": "Regular expression matched against labels.",
          "type": "string"
        },
        "metadata_field": {
          "description": "Top-level metadata equality filter as `key=value`, split on the first `=`. Repeatable. An invalid key is a 400.",
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "parent": {
          "description": "Restrict to recursive descendants of this issue.",
          "type": "string"
        },
        "priority": {
          "description": "Exact priority (0 is a real value, not \"unset\").",
          "type": "integer"
        },
        "sort": {
          "default": "priority",
          "description": "Ready-work ordering. `priority` is priority-first; `hybrid` orders recent issues by priority and older ones by age; `oldest` is creation order. An unrecognized value is a 400.\n\nThe default is the one `bd ready --sort` registers, so a client swapping `bd ready --json` for this operation gets the same items in the same order. The storage layer treats an EMPTY policy as `hybrid`, but that fallback is unreachable from the CLI and is NOT this parameter's default: `hybrid` demotes older high-priority work, so defaulting to it would change the item SET as soon as `limit` truncates \u2014 silently, and only for the clients this API exists to migrate.",
          "enum": [
            "hybrid",
            "priority",
            "oldest"
          ],
          "type": "string"
        },
        "type": {
          "description": "Issue type. The only normalization is shorthand ALIAS expansion, exactly what `bd ready --type` does: `mr` \u2192 `merge-request`, `feat` \u2192 `feature`, `mol` \u2192 `molecule`, `enhancement` \u2192 `feature`, `dec`/`adr` \u2192 `decision`. Every other value is used as written \u2014 there is NO plural folding, so `bugs` is not `bug`.\n\nAn unrecognized type is not an error here: the type vocabulary is workspace-configurable, and `bd ready` does not validate it either, so it simply matches nothing and `items` comes back empty. (The list operation differs \u2014 `bd list` DOES validate the type, so `GET /v0/beads/issues?type=bugs` is a 400.)\n\nWhen set, `exclude_type` is ignored, and so are the default type exclusions described above.",
          "type": "string"
        },
        "unassigned": {
          "description": "Only issues with no assignee.",
          "type": "boolean"
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
    "body": {
      "$ref": "#/$defs/ClaimNextRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
    },
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query"
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.claim_next` resource and `sinnix-agent-gateway catalog beads.claim_next --schema`.

Examples:

Claim the next ready issue:

```json
{
  "body": {
    "actor": "example-worker"
  },
  "idempotency_key": "example-claimNextIssue-1",
  "project": {
    "project": "sinnix"
  },
  "query": {
    "sort": "priority",
    "unassigned": true
  }
}
```

### `beads.close`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "CloseIssueRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is closing the issue. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value reaches stored columns, event-stream attribution and the storage commit message, so an unvalidated newline would forge audit-trail lines.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "expected_version": {
          "description": "Requires the row's revision to equal this value BEFORE the close. A miss refuses the whole request with `409 precondition_failed` and writes nothing \u2014 `UpdateIssueRequest.expected_version`'s contract, on the operation that closes one row.\n\nIT IS CHECKED BEFORE THE IDEMPOTENT RE-CLOSE, which is the one place this guard differs from the update's. A re-close of a row somebody else has moved since the caller read it is a `409` and not the 200-with-`already_closed` the same body earns without a guard: a replay whose premise has expired is a refusal the caller wants to see, and it is the only way `already_closed` can be trusted as \"nothing has happened here since\".\n\nThe token is the `revision` this operation's own response carries. Compose the next expectation from the value a write ANSWERED with, never from a number the client incremented itself: the token is OPAQUE and compared for equality alone, so it has no predecessor a client can compute. A first guarded close seeds itself from `GET /v0/beads/issues/{id}`'s `revision` \u2014 the read that sources a guard \u2014 or, for a chain already mid-flight, from an unguarded lifecycle write or `POST /v0/beads/issues:batchApply`'s `ApplyItemResult.revision`.\n\nDECODE IT AS A 64-BIT INTEGER, for the reason `UpdateIssueRequest.expected_version` spells out: an IEEE-754-double parser corrupts it silently, and the corruption only surfaces as a `precondition_failed` on the NEXT request.",
          "type": "integer"
        },
        "force": {
          "default": false,
          "description": "Bypass close policy \u2014 the open-children refusal and the live-blocker refusal \u2014 and nothing else. The refusals are the ROLE's, so this endpoint cannot skip a guard by forgetting one exists. A forced close still reports `open_children`.\n\nIT BYPASSES POLICY, NEVER A PRECONDITION. `expected_version` is still checked with it set, for the reason `issueops.CloseRequest.Force` gives: a caller saying \"close it anyway\" has said nothing about whether the row is still the one it read.",
          "type": "boolean"
        },
        "reason": {
          "description": "Why the issue is closed. Stored on the issue and read back as `close_reason`. THE FIRST CLOSE WINS: an idempotent re-close writes neither this nor `session`, so a replayed close cannot rewrite the record of why the work ended. Refused for control characters, and bounded by what the column holds rather than by the number above.",
          "maxLength": 255,
          "type": "string"
        },
        "session": {
          "description": "The working session that closed the issue, stored and read back as `closed_by_session`, under the same first-close-wins rule and the same bounds as `reason`.",
          "maxLength": 255,
          "type": "string"
        }
      },
      "required": [
        "actor"
      ],
      "type": "object"
    },
    "Path": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "body": {
      "$ref": "#/$defs/CloseIssueRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.close` resource and `sinnix-agent-gateway catalog beads.close --schema`.

Examples:

Close one issue:

```json
{
  "body": {
    "actor": "example-worker",
    "expected_version": 7,
    "reason": "Acceptance checks passed"
  },
  "idempotency_key": "example-closeIssue-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.metadata.compare_set`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "CompareAndSetMetadataRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is performing the swap. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. It reaches the update event's attribution and the storage commit message, so an unvalidated newline would forge audit-trail lines.\n\nIt is REQUIRED here rather than optional, because a swap is a coordination write between racing callers and the one question asked of its history entry afterwards is which of them won.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "expected": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "key": {
          "description": "The single metadata key to read and write. It must match the workspace's metadata-key syntax \u2014 a letter or underscore, then letters, digits, underscores, dots and slashes \u2014 so a key the query layer could not later spell is refused rather than written.\n\nONE KEY, NOT A PATH: a dotted key like `gc.lease` names a top-level key spelled with a dot, not a nested field. The metadata object's nesting is VALUE structure, and this operation swaps whole values.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "value": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "actor",
        "key"
      ],
      "type": "object"
    },
    "MetadataValue": {
      "anyOf": [
        {},
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "One metadata value: ANY JSON value \u2014 string, number, boolean, null, array or object \u2014 because typed values enter through the explicit JSON metadata path and persist in older rows. It is not a string, and a client must not decode it as one.\n\nWhere a member of this type is OMITTED, the key is absent; where it is present holding `null`, the key exists and holds null. Those are different states and this surface reports both."
    },
    "Path": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "body": {
      "$ref": "#/$defs/CompareAndSetMetadataRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.metadata.compare_set` resource and `sinnix-agent-gateway catalog beads.metadata.compare_set --schema`.

Examples:

Conditionally set one metadata key on an issue:

```json
{
  "body": {
    "actor": "example-worker",
    "expected": "pending",
    "key": "verification",
    "value": "passed"
  },
  "idempotency_key": "example-compareAndSetMetadata-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.dependencies.count`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "Query1": {
      "additionalProperties": false,
      "properties": {
        "direction": {
          "description": "Which end of the edge the anchors sit on. `out` counts what each anchor DEPENDS ON \u2014 the direction `bd dep list` reads and the number `bd show` prints as the dependency count. `in` counts what depends on it.\n\nIT IS REQUIRED, and that is the one deliberate unfriendliness on this request. The two answers are about DIFFERENT EDGE SETS, and a workspace where most issues have edges in only one direction returns the same number for both often enough that a caller who meant the other one would not notice for a long time. An absent or unrecognized value is a 400 `invalid_argument` with `param: \"direction\"`, never a count in some default direction.\n\nThe vocabulary is CLOSED \u2014 unlike `type` below \u2014 because it is a property of the edge's shape rather than of a workspace's configuration.",
          "enum": [
            "out",
            "in"
          ],
          "type": "string"
        },
        "issue_id": {
          "description": "The anchors to count around. Repeat the parameter; at least one is required and at most 100 are accepted, and either bound is a 400 `invalid_argument` with `param: \"issue_id\"`, `reason: \"invalid_value\"`.\n\nEach value must be an EXACT canonical issue id, for the reason `GET /v0/beads/dependencies` gives. A value that matches nothing is reported on its own anchor rather than refused. An EMPTY value is a 400: the empty string names nothing a caller can have meant, and reporting it as a missing anchor would put a nameless row in an answer keyed by name.\n\nRepeats collapse onto the first mention \u2014 a second entry carries no second fact and would only invite a caller summing the result to count the same edges twice.",
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        },
        "status": {
          "description": "Count only edges whose DEPENDENT \u2014 the issue at the source end, the one doing the depending \u2014 is in this stored status. Empty means every status.\n\nIT IS LEGAL ONLY WITH `direction=in`. Sending it beside `direction=out` is a 400 `invalid_argument` with `param: \"status\"` and `reason: \"invalid_value\"`, rather than a filter that is quietly ignored. The asymmetry is the substrate's and `issueops.EdgeCountRequest.Status` states why: narrowing by status joins the far end of the edge to the row holding its status, and an OUTBOUND edge's far end may be an `external:` reference or an id belonging to another repository \u2014 rows this database does not hold \u2014 so the filter would silently drop every dangling edge.\n\nIt is ONE status, not a comma-separated OR set, and it is NOT validated against the workspace vocabulary: an unrecognized name matches nothing and counts 0 rather than failing, exactly as `GET /v0/beads/issues:count`'s `status` does. A scripted caller counting a status its workspace has since dropped reads 0 and should keep reading 0.",
          "type": "string"
        },
        "type": {
          "description": "Edge types to include. Repeat the parameter. Empty means every type.\n\n`GET /v0/beads/dependencies`'s `type` exactly: the vocabulary is OPEN, so an unrecognized value is not an error and simply matches no edge, while a value no edge could ever carry \u2014 empty, or longer than the column \u2014 is a 400 `invalid_argument`.\n\nThe filter narrows EDGES, never anchors. An anchor whose every edge it rejects comes back present with a count of 0, which is a different fact from an anchor that is not there.",
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      },
      "required": [
        "direction",
        "issue_id"
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
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query1"
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
    "query",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.dependencies.count` resource and `sinnix-agent-gateway catalog beads.dependencies.count --schema`.

Examples:

Count the dependency edges around several issues:

```json
{
  "project": {
    "project": "sinnix"
  },
  "query": {
    "direction": "out",
    "issue_id": [
      "sinnix-abc1"
    ],
    "type": [
      "blocks"
    ]
  }
}
```

### `beads.create`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "CreateIssueDependency": {
      "additionalProperties": false,
      "description": "One edge created with the issue. It carries `reverse` where `BatchCreateDependency` does not, because that operation's items have no id a target could point back at and this one's issue does.",
      "properties": {
        "metadata": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "reverse": {
          "default": false,
          "description": "Writes the edge from `target_id` TO the new issue rather than from it. It is what lets a create declare an edge that points INTO the row being minted \u2014 the id no caller could have spelled beforehand \u2014 and it is the member that makes `dependency_cycle` reachable on this operation at all.",
          "type": "boolean"
        },
        "target_id": {
          "description": "The other endpoint of the edge.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "description": "The edge type, from the same OPEN vocabulary `Dependency.type` carries: checked for BEING a storable value, never for membership of a known-types list, so a workspace's own type passes.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "target_id",
        "type"
      ],
      "type": "object"
    },
    "CreateIssueRequest": {
      "additionalProperties": false,
      "description": "One issue, its parent, its explicit edges and its waits-for gate, created as one act.\n\nIt is FLAT rather than nesting the issue's fields under an `issue` member, unlike `UpdateIssueRequest`'s `patch`: a patch has to distinguish a member that is absent from one set to its zero value, and a create has no such distinction to make \u2014 an absent member is the workspace default, which is the same answer a nested object would have given.\n\nThe issue members mirror `ApplyCreateItem` exactly, minus that schema's two plan-only members (`key` and `metadata_refs`, which name items of a request this operation has only one of). What this adds is the edge vocabulary that operation moves into `dep_add` items: `parent_id`, `inherit_labels_from_parent`, `dependencies` and `waits_for`.",
      "properties": {
        "acceptance_criteria": {
          "type": "string"
        },
        "actor": {
          "description": "Who is creating the issue. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value reaches the created edges' author column, the history entry's attribution and the storage commit message, so an unvalidated newline would forge audit-trail lines.\n\nIt is NOT the issue's `created_by`, which this operation does not publish: this is the caller-asserted provenance of the ACT, and the row's own author column is left to the implementation.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "assignee": {
          "maxLength": 255,
          "type": "string"
        },
        "defer_until": {
          "description": "RFC 3339. The issue is hidden from ready work until then. Not nullable, for `estimated_minutes`' reason.",
          "format": "date-time",
          "type": "string"
        },
        "dependencies": {
          "description": "The complete set of explicit edges created with the issue. Authoritative, not a patch. Every edge is written in the same transaction as the row, so an edge this request cannot write means no issue either.\n\nA TARGET NEED NOT BE A ROW THIS DATABASE HOLDS: an `external:` reference and an id belonging to another repository are legitimate targets, so only an absence this database can SEE is refused \u2014 `ApplyDepAddItem`'s rule, unchanged.",
          "items": {
            "$ref": "#/$defs/CreateIssueDependency"
          },
          "maxItems": 100,
          "type": "array"
        },
        "description": {
          "type": "string"
        },
        "design": {
          "type": "string"
        },
        "due_at": {
          "description": "RFC 3339. Not nullable, for `estimated_minutes`' reason.",
          "format": "date-time",
          "type": "string"
        },
        "ephemeral": {
          "default": false,
          "description": "Creates the issue on the EPHEMERAL plane rather than the durable one, exactly as it does for `POST /v0/beads/issues:batchApply`. Mutually exclusive with `no_history`.",
          "type": "boolean"
        },
        "estimated_minutes": {
          "description": "An estimate in minutes. Absent leaves it unset. NOT nullable, unlike `IssuePatchBody.estimated_minutes`: a create has nothing to clear, so `null` here would be a second spelling of omission and is a `400`.",
          "type": "integer"
        },
        "external_ref": {
          "description": "e.g. `gh-9`. Not nullable, for `estimated_minutes`' reason.",
          "maxLength": 255,
          "type": "string"
        },
        "force_id_prefix": {
          "default": false,
          "description": "Permits an explicit `id` outside the workspace's configured issue prefix. It bypasses ONLY that check: it is not a force on the create-only guard, so an occupied id is still a `409`.",
          "type": "boolean"
        },
        "id": {
          "description": "An explicit id for the new row, CREATE-ONLY: an id that already names a stored row is a `409` `already_exists` and nothing is written \u2014 never an adoption and never an overwrite. It is checked against the workspace's configured issue prefix unless `force_id_prefix` is set. Absent is the ordinary case and the server mints one.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "inherit_labels_from_parent": {
          "default": false,
          "description": "Copies the parent's labels onto the new issue at creation, on top of `labels`. It has no effect without `parent_id`.\n\nThe DEFAULT IS FALSE and diverges from `bd create --parent`, whose default is to inherit. A wire caller sends what it means: this operation has no `--no-inherit-labels` to turn off, and a create that silently acquired labels the request never named would be a set the caller has to read back to learn.",
          "type": "boolean"
        },
        "issue_type": {
          "description": "Issue type. Spelled `issue_type` rather than `type`, matching the member `Issue` carries, and validated against the built-ins plus the workspace's configured custom types by the ROLE \u2014 this server cannot read that vocabulary without a transaction, so it checks only what this schema declares and an unknown one arrives as a `400`.\n\nSEND ONE. The member is optional in this schema and the role validates the EMPTY type against the same vocabulary as any other, where it is neither a built-in nor a configured type \u2014 so an omitted `issue_type` is refused with everything else the request asked for. It stays optional because the vocabulary belongs to the workspace and a deployment may configure a default this server cannot read, but it is not optional in practice on any workspace shipped today. `POST /v0/beads/issues:batchCreate` has the same property and does not say so, which is why this member does.",
          "maxLength": 255,
          "type": "string"
        },
        "labels": {
          "description": "The complete label set the issue is created with. Authoritative, not a patch \u2014 a create has nothing to add to. `inherit_labels_from_parent` adds the parent's labels on top of it.",
          "items": {
            "$ref": "#/$defs/Label"
          },
          "type": "array"
        },
        "metadata": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "no_history": {
          "default": false,
          "description": "Creates the issue on the ephemeral plane WITHOUT history, and without the garbage collection an ordinary ephemeral row is eligible for. Mutually exclusive with `ephemeral`.",
          "type": "boolean"
        },
        "notes": {
          "type": "string"
        },
        "owner": {
          "description": "The human owner, which is a different member from `assignee`: the assignee is who is working it now, the owner is who it is attributed to.",
          "maxLength": 255,
          "type": "string"
        },
        "parent_id": {
          "description": "Creates a typed `parent-child` edge from the new issue to this target. It must not duplicate an edge `dependencies` already spells; naming the same pair twice with two types is a `400`.",
          "maxLength": 255,
          "type": "string"
        },
        "priority": {
          "description": "0 is P0/critical. Absent means the workspace default.",
          "maximum": 4,
          "minimum": 0,
          "type": "integer"
        },
        "sender": {
          "description": "Who sent this, for the message-shaped rows an orchestrator creates. Stored verbatim and interpreted by nothing on this surface.",
          "maxLength": 255,
          "type": "string"
        },
        "status": {
          "description": "The status the issue is created in, from this workspace's own configured vocabulary. Absent means the workspace's own default, which is `open` today \u2014 unlike `issue_type`, the role fills this one in before it validates.",
          "maxLength": 255,
          "type": "string"
        },
        "title": {
          "description": "The issue's title. Must not be blank after trimming.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "waits_for": {
          "$ref": "#/$defs/CreateIssueWaitsFor"
        }
      },
      "required": [
        "actor",
        "title"
      ],
      "type": "object"
    },
    "CreateIssueWaitsFor": {
      "additionalProperties": false,
      "description": "A typed `waits-for` edge from the new issue to a spawner whose children gate it. It records a readiness primitive; it does not define scheduling or execution policy.\n\nIT IS A TYPED MEMBER HERE AND A METADATA BLOB ON `POST /v0/beads/issues:batchApply`, and the difference follows the ROLE rather than taste: `CreateRequest.WaitsFor` is a typed field that gets the gate defaulted and the \"must not duplicate an explicit edge\" check, while that operation's `dep_add` item is one generic edge with no typed field to reach. One spelling per operation, and each is its role's.",
      "properties": {
        "gate": {
          "description": "The readiness condition: `all-children` or `any-children`. Absent or empty defaults to `all-children`. A value that is neither is refused by the ROLE and reaches the client as a `400`.",
          "maxLength": 255,
          "type": "string"
        },
        "spawner_id": {
          "description": "The dependency target whose children are observed. It must not duplicate an edge `dependencies` or `parent_id` already spells.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "spawner_id"
      ],
      "type": "object"
    },
    "Label": {
      "maxLength": 255,
      "type": "string"
    },
    "MetadataValue": {
      "anyOf": [
        {},
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "One metadata value: ANY JSON value \u2014 string, number, boolean, null, array or object \u2014 because typed values enter through the explicit JSON metadata path and persist in older rows. It is not a string, and a client must not decode it as one.\n\nWhere a member of this type is OMITTED, the key is absent; where it is present holding `null`, the key exists and holds null. Those are different states and this surface reports both."
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
    "body": {
      "$ref": "#/$defs/CreateIssueRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.create` resource and `sinnix-agent-gateway catalog beads.create --schema`.

Examples:

Create one issue:

```json
{
  "body": {
    "actor": "example-worker",
    "issue_type": "task",
    "priority": 2,
    "title": "Add bounded result paging"
  },
  "idempotency_key": "example-createIssue-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.memory.forget`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Path4": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Exact memory key, used verbatim. It occupies one path segment and is percent-decoded once. Keys may contain spaces, dots and unicode \u2014 the plane stores what `bd remember --key` was given \u2014 and a key carrying a CONTROL character is refused here rather than looked up; see the operation description.",
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "key"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path4"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.memory.forget` resource and `sinnix-agent-gateway catalog beads.memory.forget --schema`.

Examples:

Forget one stored memory:

```json
{
  "idempotency_key": "example-forgetMemory-1",
  "path": {
    "key": "reader-checks"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.graph`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "Query2": {
      "additionalProperties": false,
      "properties": {
        "direction": {
          "default": "down",
          "description": "Which way to follow edges. `down` (the default) walks what the root DEPENDS ON; `up` walks what depends ON it; `both` walks each way and returns one list.\n\nFor `both` the two walks are independent and the answer is their concatenation: every up node except the root, then the whole down tree beginning with the root. The root appears once. The two halves may repeat a node between them \u2014 an issue that both blocks and is blocked by something in the other half \u2014 so a client aggregating `items` must not assume the ids are distinct. Both walks see ONE database state.\n\nAny other value is a 400 `invalid_argument`: the vocabulary is closed.",
          "enum": [
            "down",
            "up",
            "both"
          ],
          "type": "string"
        },
        "max_depth": {
          "default": 50,
          "description": "How many LEVELS to descend, counting the root as level one: `max_depth=1` is the root alone. A node beyond the bound is ABSENT rather than present and flagged.\n\nZero and negative values are a 400 `invalid_argument` rather than \"unbounded\": the answer to an unbounded recursive walk on a large workspace is the request that takes the database down.",
          "minimum": 1,
          "type": "integer"
        },
        "root_id": {
          "description": "The issue to walk from. It must be an EXACT canonical issue id: there is no fuzzy, prefix or substring resolution on this surface, for the reason `GET /v0/beads/issues/{id}` gives. An empty value is a 400 `invalid_argument`; a value that matches no issue and no wisp is a 404 `not_found`, because there is one anchor here and no other answer to preserve.",
          "type": "string"
        },
        "status": {
          "description": "Prune the walked tree to the nodes carrying this status AND the ancestor chain of each survivor, so the answer is still a tree.\n\nIt is a POST-WALK PRUNE, not a filter on the walk, and the difference is observable: a matching node BEHIND a non-matching one is still reached, and the non-matcher is kept as its ancestor. A prune that matches nothing returns NO items at all, root included.\n\nThe value is not checked against the workspace's status vocabulary; an unrecognized status simply matches nothing.",
          "type": "string"
        }
      },
      "required": [
        "root_id"
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
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query2"
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
    "query",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.graph` resource and `sinnix-agent-gateway catalog beads.graph --schema`.

Examples:

Walk the dependency tree of one issue:

```json
{
  "project": {
    "project": "sinnix"
  },
  "query": {
    "direction": "both",
    "max_depth": 3,
    "root_id": "sinnix-abc1"
  }
}
```

### `beads.memory.get`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Path4": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Exact memory key, used verbatim. It occupies one path segment and is percent-decoded once. Keys may contain spaces, dots and unicode \u2014 the plane stores what `bd remember --key` was given \u2014 and a key carrying a CONTROL character is refused here rather than looked up; see the operation description.",
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "key"
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
    "path": {
      "$ref": "#/$defs/Path4"
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
    "path",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.memory.get` resource and `sinnix-agent-gateway catalog beads.memory.get --schema`.

Examples:

Get one stored memory:

```json
{
  "path": {
    "key": "reader-checks"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.blockers`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "Query3": {
      "additionalProperties": false,
      "properties": {
        "issue_id": {
          "description": "The issues to annotate. Repeat the parameter; at least one is required and at most 100 are accepted, and either bound is a 400 `invalid_argument` with `param: \"issue_id\"`, `reason: \"invalid_value\"`.\n\nEach value must be an EXACT canonical issue id: there is no fuzzy, prefix or substring resolution on this surface, for the reason `GET /v0/beads/issues/{id}` gives. A value that matches nothing gets a bare entry rather than being refused. An empty value is a 400.\n\nRepeats collapse: an id named twice is one entry, at the position of its first mention.",
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        }
      },
      "required": [
        "issue_id"
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
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query3"
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
    "query",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.blockers` resource and `sinnix-agent-gateway catalog beads.blockers --schema`.

Examples:

Read the blocking decoration of several issues:

```json
{
  "project": {
    "project": "sinnix"
  },
  "query": {
    "issue_id": [
      "sinnix-abc1"
    ]
  }
}
```

### `beads.dependencies`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "Query4": {
      "additionalProperties": false,
      "properties": {
        "issue_id": {
          "description": "The issues to read edges for. Repeat the parameter; at least one is required and at most 100 are accepted, and either bound is a 400 `invalid_argument` with `param: \"issue_id\"`, `reason: \"invalid_value\"`.\n\nEach value must be an EXACT canonical issue id: there is no fuzzy, prefix or substring resolution on this surface, for the reason `GET /v0/beads/issues/{id}` gives. A value that matches nothing is reported in `missing` rather than refused. An empty value is a 400.\n\nRepeats collapse: an id named twice is one entry in `missing` at most once, and its edges appear once.",
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "minItems": 1,
          "type": "array"
        },
        "type": {
          "description": "Edge types to include. Repeat the parameter. Empty means every type.\n\nThe vocabulary is OPEN \u2014 a workspace configures its own edge types \u2014 so an unrecognized value is not an error here: it simply matches no edge. What IS refused, with a 400 `invalid_argument`, is a value no edge could ever carry: empty, or longer than the column.\n\nThe filter narrows EDGES, never the named issues. An issue whose every edge the filter rejects is still not in `missing`.",
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      },
      "required": [
        "issue_id"
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
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query4"
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
    "query",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.dependencies` resource and `sinnix-agent-gateway catalog beads.dependencies --schema`.

Examples:

List the stored dependency edges of several issues:

```json
{
  "project": {
    "project": "sinnix"
  },
  "query": {
    "issue_id": [
      "sinnix-abc1"
    ],
    "type": [
      "blocks"
    ]
  }
}
```

### `beads.cycles`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.cycles` resource and `sinnix-agent-gateway catalog beads.cycles --schema`.

Examples:

List dependency cycles:

```json
{
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.memories`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "Query5": {
      "additionalProperties": false,
      "properties": {
        "search": {
          "description": "Narrows the answer to memories that MATCH: a memory matches when the lowercase of its key, or the lowercase of its value, contains the lowercase of this term. Absent or empty means everything, and a term nothing matches is a `200` with an empty `items`.\n\nIT IS A SUBSTRING MATCH, NOT THE `issues:query` EXPRESSION LANGUAGE, and it is spelled `search` rather than `q` FOR THAT REASON. On `GET /v0/beads/issues:query`, `q` is a boolean expression over issue fields that is refused when it does not parse; here there is nothing to parse, no vocabulary and no refusal \u2014 every string is a legal search term, `status=open` included, and it is matched literally. Two names because two questions: a client that sent this operation the other `q` would otherwise get a literal substring search back instead of an error.\n\nThe term reaches the role UNFOLDED. Case folding is the role's, so that this surface and `bd memories` cannot come to disagree about what matching means; a client sends what its user typed.",
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
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query5"
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
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.memories` resource and `sinnix-agent-gateway catalog beads.memories --schema`.

Examples:

List the workspace's stored memories:

```json
{
  "project": {
    "project": "sinnix"
  },
  "query": {
    "search": "reader"
  }
}
```

### `beads.related`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `query`. Owner: `beads`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Path6": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "Query6": {
      "additionalProperties": false,
      "properties": {
        "direction": {
          "description": "Which way this issue's edges are walked. `out` answers the issues it DEPENDS ON \u2014 the `dependencies` member of `GET /v0/beads/issues/{id}`. `in` answers the issues that depend on it \u2014 that read's `dependents` member.\n\nIT IS REQUIRED AND HAS NO DEFAULT, on `GET /v0/beads/dependencies:count`'s terms and for the reason `issueops.RelationDirection` gives: the two answers have the same shape and the same member names, so a caller handed the inverse graph has nothing to notice. An absent or unrecognized value is a 400 `invalid_argument` with `param: \"direction\"`, never a walk in some default direction.\n\nThe vocabulary is CLOSED \u2014 unlike `type` below \u2014 because it is a property of the edge's shape rather than of a workspace's configuration.",
          "enum": [
            "out",
            "in"
          ],
          "type": "string"
        },
        "type": {
          "description": "Edge types to include. Repeat the parameter. Empty means every type.\n\n`GET /v0/beads/dependencies`'s `type` exactly: the vocabulary is OPEN, so an unrecognized value is not an error and simply matches no edge, while a value no edge could ever carry \u2014 empty, or longer than the column \u2014 is a 400 `invalid_argument` with `param: \"type\"`.\n\nThe filter narrows EDGES, never the anchor. An issue whose every edge it rejects is answered with an empty `items` and not with a 404, which is a different fact from an id that names nothing.",
          "items": {
            "type": "string"
          },
          "type": "array"
        }
      },
      "required": [
        "direction"
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
    "path": {
      "$ref": "#/$defs/Path6"
    },
    "project": {
      "$ref": "#/$defs/ProjectLocator"
    },
    "query": {
      "$ref": "#/$defs/Query6"
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
    "path",
    "query",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.related` resource and `sinnix-agent-gateway catalog beads.related --schema`.

Examples:

List one issue's neighbors in a named direction:

```json
{
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  },
  "query": {
    "direction": "out",
    "type": [
      "blocks"
    ]
  }
}
```

### `beads.unclaim`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Path6": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "ReleaseIssueRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is releasing the claim. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value reaches the event the release records and the storage commit message, so an unvalidated newline would forge audit-trail lines.\n\nIt is REQUIRED, and for one reason beyond the audit trail: a release is the moment work stops being owned, and the one question asked of its history entry afterwards is who let it go. On the unconditional path it is ALSO the ownership fence's subject \u2014 see the operation description.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "expected_assignee": {
          "description": "Compare-and-set on the holder: the release proceeds only while the issue is still assigned to this actor, and otherwise refuses with `409` / `precondition_failed` naming this value, having written nothing.\n\nA MATCH REPLACES THE OWNERSHIP FENCE, so `actor` need not be the holder. Sending it beside `force` is a 400: the two are answers to the same question and they disagree.\n\nTHE COMPARISON IS SEPARATOR-INSENSITIVE AND NOTHING ELSE. A run of `.`, `_` or `-` matches any other such run, so `agent-a`, `agent_a` and `agent.a` are one holder \u2014 that is deliberate, so a caller naming the holder under a different layer's spelling is a match rather than a mismatch. THE ONE EXCEPTION IS AN EXACT `--` RUN: that is gascity's session-name encoding of a rig-qualified agent's `/`, so it decodes to `/` instead of collapsing. `a--b` matches `a/b`, and no longer matches `a__b` or `a-b`. Those name different identities \u2014 `a--b` is the agent `b` on rig `a`, `a__b` is the dotted alias `a.b` \u2014 so treating them as one holder was a widening, and removing it is the point of the exception. Longer or mixed runs, `__` included, still collapse. NOTHING ELSE IS FORGIVEN: the value is not trimmed and not case-folded, so `\" agent-a\"` and `Agent-a` are both refusals. The server trims only far enough to tell a blank expectation from a real one and never sends the trimmed form on, so a caller that pads its expectation loses EVERY time rather than intermittently. Compose it from a holder a read gave you.\n\nTHE EMPTY STRING IS A 400, and this is the one place this member disagrees with `UpdateIssueRequest.expected_assignee`, where an empty string is a real guard meaning \"expected unassigned\". Here \"release a row nobody holds\" describes no release at all; a caller that wants to assert a row is unheld is asking a READER a question, not asking this operation to do nothing. Absent, and only absent, selects the unconditional path.\n\nIT IS NOT LENGTH- OR PATTERN-BOUNDED the way `actor` is, and the asymmetry is deliberate: this value is COMPARED and never stored, so a value no assignee column could hold simply cannot match, and refusing it at the edge would be a refusal the role does not have.",
          "type": "string"
        },
        "force": {
          "default": false,
          "description": "Bypass the ownership fence, so an actor that is not the holder may release the claim. It is the escape hatch `bd unclaim --force` spells, for an abandoned claim whose holder crashed.\n\nIT BYPASSES THE FENCE AND NOTHING ELSE. It does not make an unheld row releasable, it does not make a closed one releasable, and it never bypasses a precondition \u2014 sending it beside `expected_assignee` is a 400 rather than a silent win for either.",
          "type": "boolean"
        }
      },
      "required": [
        "actor"
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
    "body": {
      "$ref": "#/$defs/ReleaseIssueRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path6"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.unclaim` resource and `sinnix-agent-gateway catalog beads.unclaim --schema`.

Examples:

Give back the claim on an issue:

```json
{
  "body": {
    "actor": "example-worker",
    "expected_assignee": "example-worker"
  },
  "idempotency_key": "example-releaseIssue-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.memory.remember`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "RememberRequest": {
      "additionalProperties": false,
      "description": "What to remember, and optionally under what key.",
      "properties": {
        "content": {
          "description": "The memory itself, stored VERBATIM: newlines, surrounding space and unicode all survive. Flattening it to one line is what a front door does when it prints, not what this plane does when it stores.\n\nEmpty after trimming is a `400`. So is content from which no key can be derived when `key` is omitted \u2014 `\"!!!\"` derives to nothing \u2014 and the recovery for that one is to send a `key`.",
          "type": "string"
        },
        "key": {
          "description": "The key to store under. OMIT IT to have the server derive one from `content`; the response's `key` is then how the caller learns where the memory landed.\n\nSupplied, it is used verbatim \u2014 no trimming, no slugging, no charset restriction. A key carrying a control character is storable this way and by `bd remember --key`, and is then unreachable through `GET`/`DELETE /v0/beads/memories/{key}`, which refuse one: see those operations.",
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
    "body": {
      "$ref": "#/$defs/RememberRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.memory.remember` resource and `sinnix-agent-gateway catalog beads.memory.remember --schema`.

Examples:

Store one memory:

```json
{
  "body": {
    "content": "The reader contract includes bounded pages and continuation tokens.",
    "key": "reader-checks"
  },
  "idempotency_key": "example-rememberMemory-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.dependencies.remove`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

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
    },
    "RemoveDependencyRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is removing the edge, under `ClaimRequest.actor`'s rules and for the same reasons: the server trims it, refuses an empty result, anything longer than 256 BYTES, and any control character including newline. It is attributed on the `dependency_removed` event a real removal records, and interpolated into the storage commit message.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "depends_on_id": {
          "description": "The edge's TARGET \u2014 the issue depended upon. An exact canonical id, under `issue_id`'s rule.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        },
        "issue_id": {
          "description": "The edge's SOURCE \u2014 the issue that depends on the other end. An EXACT canonical id: there is no fuzzy, prefix or substring resolution on this surface.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "actor",
        "depends_on_id",
        "issue_id"
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
    "body": {
      "$ref": "#/$defs/RemoveDependencyRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.dependencies.remove` resource and `sinnix-agent-gateway catalog beads.dependencies.remove --schema`.

Examples:

Remove one dependency edge:

```json
{
  "body": {
    "actor": "example-worker",
    "depends_on_id": "sinnix-abc1",
    "issue_id": "sinnix-abc2"
  },
  "idempotency_key": "example-removeDependency-1",
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.reopen`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "Path6": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "ReopenIssueRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is reopening the issue. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value reaches the `reopened` event's attribution and the storage commit message, so an unvalidated newline would forge audit-trail lines.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "expected_version": {
          "description": "Requires the row's revision to equal this value BEFORE the reopen. A miss refuses the whole request with `409 precondition_failed` and writes nothing \u2014 `CloseIssueRequest.expected_version`'s contract, on the close's mirror.\n\nIT IS CHECKED BEFORE THE NON-DONE NO-OP, the mirror of the close's check-before-the-idempotent-re-close, and for the same reason: a reopen of a row somebody else has moved is a `409` rather than the 200-with-`already_open` the same body earns unguarded, which is what lets `already_open` be read as \"nothing has happened here since\".\n\nThe token is the `revision` this operation's own response carries; compose the next expectation from a value a write ANSWERED with and never from one the client computed. DECODE IT AS A 64-BIT INTEGER, for the reason `UpdateIssueRequest.expected_version` spells out.",
          "type": "integer"
        },
        "reason": {
          "description": "Why the issue is being reopened. Recorded on the `reopened` EVENT this move records \u2014 not on a field of the issue, and not carried in the response, so a caller that wants it back reads the issue's events. Refused for control characters, and bounded by what the column holds rather than by the number above.",
          "maxLength": 255,
          "type": "string"
        }
      },
      "required": [
        "actor"
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
    "body": {
      "$ref": "#/$defs/ReopenIssueRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path6"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.reopen` resource and `sinnix-agent-gateway catalog beads.reopen --schema`.

Examples:

Reopen one issue:

```json
{
  "body": {
    "actor": "example-worker",
    "expected_version": 8,
    "reason": "A pagination regression remains"
  },
  "idempotency_key": "example-reopenIssue-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `beads.update`

The native Beads operation owns validation and transaction semantics. Input fields come from its published OpenAPI contract. beads.changeset applies one project's ordered batch atomically; separate projects require separate batches. Interrupted effects remain indeterminate and are never automatically retried.

Family: `change`. Owner: `beads`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.get`, `beads.query`.

Input schema:

```json
{
  "$defs": {
    "AddLabel": {
      "maxLength": 255,
      "type": "string"
    },
    "ApplyMetadataPatch": {
      "additionalProperties": false,
      "description": "A metadata edit. `replace` is mutually exclusive with the other three; without it the edits apply as `merge`, then `set` in key order, then `unset`, so UNSETTING A KEY WINS over setting or merging it. Sending `replace` beside any of the others is a `400`.\n\n`replace` replaces the whole document. Present holding `null`, `{}` or an empty value CLEARS metadata \u2014 and clearing STORES THE EMPTY JSON DOCUMENT rather than SQL null, so \"created with no metadata\" and \"given metadata and then cleared\" are the same stored value; a reader must treat absent, empty and `{}` as one value on the way out. `merge` must be a nonempty JSON OBJECT and is merged into the current document.",
      "properties": {
        "merge": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "replace": {
          "anyOf": [
            {
              "$ref": "#/$defs/MetadataValue"
            },
            {
              "type": "null"
            }
          ]
        },
        "set": {
          "additionalProperties": {
            "anyOf": [
              {
                "$ref": "#/$defs/MetadataValue"
              },
              {
                "type": "null"
              }
            ]
          },
          "description": "Individual top-level keys to write, in deterministic key order. A value present holding `null` writes JSON null; a key is removed with `unset`, never by sending a null here.",
          "type": "object"
        },
        "unset": {
          "description": "Top-level keys to remove, applied after every other edit.",
          "items": {
            "$ref": "#/$defs/UnsetItem"
          },
          "type": "array"
        }
      },
      "type": "object"
    },
    "IssuePatchBody": {
      "additionalProperties": false,
      "description": "The fields to write. Every member is optional and PRESENCE is the signal: a member present is written, a member absent is untouched. An empty object is a `400` \u2014 a write that writes nothing is a client bug.\n\nThis is a deliberate SUBSET of the fields an issue carries; the members it does not spell are future surface rather than oversights, and `updateIssue`'s own description says which and why.\n\nIt now agrees with `ApplyPatchBody` on every member it publishes, and the two differ only in the SHAPE of two of them: `labels` is complete replacement here and an ordered add/remove/replace patch there, because that operation edits a set it did not compose. Everything else \u2014 down to the `metadata` algebra and the four nullable members \u2014 is one definition, so a caller cannot get a different answer for the same edit depending on which operation it sent.",
      "properties": {
        "acceptance_criteria": {
          "type": "string"
        },
        "add_labels": {
          "description": "Labels to add, applied AFTER any `labels` replacement.\n\nIT IS NOT MUTUALLY EXCLUSIVE WITH `labels`, and that is the difference from `append_notes`, which is. The role defines an order over all three label edits, so sending a replacement and an addition together has a defined result; notes have no such algebra, so there the two are a contradiction and are refused.\n\nIT IS WHY THIS PAIR EXISTS. A caller that reads a row, adds one label and writes the whole set back silently drops any label another writer added in between \u2014 and `bd label add` and every agent that tags work concurrently are exactly that caller. A replacement can only be composed safely by a writer that knows it is alone.\n\nRepetition is free: a label named twice is applied once, and adding one the issue already carries changes no labels. (Whether the RESPONSE reports `changed: false` is a fact about the whole patch \u2014 see `remove_labels`.) An EMPTY-STRING entry is DROPPED rather than refused \u2014 a label row carrying `\"\"` renders as nothing and matches nothing, so writing one would only store junk, and refusing the whole update would let one stray entry fail an otherwise-good edit.",
          "items": {
            "$ref": "#/$defs/AddLabel"
          },
          "type": "array"
        },
        "append_notes": {
          "description": "Appends to the notes rather than replacing them. Mutually exclusive with `notes`.",
          "type": "string"
        },
        "assignee": {
          "description": "The assignee. A transfer away from a live foreign in-progress owner is refused with `409 already_claimed` unless `force_assignee_transfer` is set or `expected_assignee` matched. Setting it to the empty string unassigns.\n\n`{id}:claim` remains the operation that ACQUIRES work: it carries its own eligibility rules and sets the status with the assignee in one act. This member is the raw write, fenced.",
          "maxLength": 255,
          "type": "string"
        },
        "defer_until": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "RFC 3339. Explicit `null` CLEARS the deferral."
        },
        "description": {
          "type": "string"
        },
        "design": {
          "type": "string"
        },
        "due_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "RFC 3339. Explicit `null` CLEARS the due date."
        },
        "estimated_minutes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "description": "Explicit `null` CLEARS the estimate."
        },
        "external_ref": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "description": "Explicit `null` CLEARS the reference."
        },
        "issue_type": {
          "description": "The issue type, from this workspace's own configured vocabulary. A type outside it is refused by the ROLE and reaches the client as a `400` \u2014 this server cannot read the vocabulary without a transaction, so it checks only what this schema declares.",
          "maxLength": 255,
          "type": "string"
        },
        "labels": {
          "description": "COMPLETE REPLACEMENT of the label set. An empty array clears every label.\n\nIt is the REPLACE half of the same ordered edit `ApplyPatchBody` spells as `labels.replace`, and `add_labels`/`remove_labels` are the other two. All three may travel together and are applied in that order \u2014 replace, then add, then remove \u2014 so REMOVAL WINS when one label appears in more than one of them. That is the role's own algebra, not this operation's arrangement of it.\n\nTHE SHAPE DIFFERS FROM `ApplyPatchBody`'s, which nests the three under one `labels` object, and the difference is historical rather than meaningful. This member shipped as a bare array; nesting it now would RE-TYPE a published member, which is the one kind of change this document has no additive route for. Two flat siblings is the shape that could be added \u2014 and it is the shape `notes` and `append_notes` already use for the same replace/increment pair.",
          "items": {
            "$ref": "#/$defs/Label"
          },
          "type": "array"
        },
        "metadata": {
          "$ref": "#/$defs/ApplyMetadataPatch"
        },
        "notes": {
          "description": "Replaces the notes. Mutually exclusive with `append_notes`; sending both is a `400`.",
          "type": "string"
        },
        "parent_id": {
          "description": "Replaces the issue's parents atomically: a nonempty value makes THAT issue the only parent, and an EMPTY STRING removes every parent-child edge the issue has. Labels are not inherited \u2014 that is a create-time choice (`CreateIssueRequest.inherit_labels_from_parent`) and a reparent does not re-run it.\n\nIT IS A GRAPH EDIT, and it earns the graph's refusals: a new parent this workspace holds no row for is a `400`, a pair that already carries an edge of another type is `409 dependency_exists`, and a move under the issue's own descendant is `409 dependency_cycle` \u2014 the PLAIN one, carrying no `issue_id`/`blocker_id`/ `blocker_is_ancestor`, because the hierarchy refusal answers only to blocking edges and this member writes a `parent-child` edge. Naming the issue itself is a `400`. One call rather than a remove-then-add pair, which is the whole reason it is here: the two-call spelling leaves the issue parentless if the second call fails.",
          "maxLength": 255,
          "type": "string"
        },
        "priority": {
          "maximum": 4,
          "minimum": 0,
          "type": "integer"
        },
        "remove_labels": {
          "description": "Labels to remove, applied AFTER `labels` and `add_labels`, so REMOVAL WINS over both.\n\nRemoving a label the issue does not carry CHANGES NO LABELS; it is not a `404` and not a conflict. Whether the RESPONSE reports `changed: false` is a fact about the whole patch, not about this member \u2014 a request that also moved a title changed the row. The same repetition and empty-string rules as `add_labels` apply, and a value longer than the column is refused here as it is there \u2014 the length rule is about what a label may BE, not about whether this particular row happens to carry one.",
          "items": {
            "$ref": "#/$defs/RemoveLabel"
          },
          "type": "array"
        },
        "status": {
          "description": "The issue's status, from this workspace's own configured vocabulary.\n\nA STATUS THAT CROSSES INTO THE DONE CATEGORY ANSWERS TO CLOSE POLICY: the update is refused with `409 not_closable` for open children or a live blocker unless `force_close_policy` is set. A done-to-done change and a move OUT of the done category are unaffected.\n\nIT IS NOT A SECOND SPELLING OF `{id}:close` AND `{id}:reopen`. Those two carry semantics a status write has nowhere to put \u2014 the reason and session under first-close-wins, the done-status normalization, the `already_closed`/`already_open` idempotence flags \u2014 and they remain the operations to reach for when what you mean is \"close this\". This member is for the edit that moves a status ALONGSIDE other fields in one transaction, which is the thing two calls cannot do. `ApplyPatchBody.status` has meant exactly this since `issues:batchApply` landed.",
          "maxLength": 255,
          "type": "string"
        },
        "title": {
          "description": "The issue's title. Must not be blank after trimming; the length bound is what the column holds.",
          "maxLength": 255,
          "minLength": 1,
          "type": "string"
        }
      },
      "type": "object"
    },
    "Label": {
      "maxLength": 255,
      "type": "string"
    },
    "MetadataValue": {
      "anyOf": [
        {},
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "One metadata value: ANY JSON value \u2014 string, number, boolean, null, array or object \u2014 because typed values enter through the explicit JSON metadata path and persist in older rows. It is not a string, and a client must not decode it as one.\n\nWhere a member of this type is OMITTED, the key is absent; where it is present holding `null`, the key exists and holds null. Those are different states and this surface reports both."
    },
    "Path6": {
      "additionalProperties": false,
      "properties": {
        "id": {
          "description": "Exact canonical issue id. No fuzzy, prefix or substring resolution.",
          "type": "string"
        }
      },
      "required": [
        "id"
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
    "RemoveLabel": {
      "maxLength": 255,
      "type": "string"
    },
    "UnsetItem": {
      "maxLength": 255,
      "type": "string"
    },
    "UpdateIssueRequest": {
      "additionalProperties": false,
      "properties": {
        "actor": {
          "description": "Who is editing the issue. `ClaimRequest.actor`'s rules exactly: the server trims it, then refuses an empty result, anything longer than 256 BYTES (the `maxLength` above counts characters \u2014 the byte limit is the binding one), and any control character including newline. The value reaches the history entry's attribution and the storage commit message, so an unvalidated newline would forge audit-trail lines.",
          "maxLength": 256,
          "minLength": 1,
          "pattern": "^[^\\u0000-\\u001F\\u007F-\\u009F\\u2028\\u2029]+$",
          "type": "string"
        },
        "expected_assignee": {
          "description": "Requires the issue's assignee to equal this value before the patch. A match AUTHORIZES the requested `patch.assignee` transfer: this compare-and-set replaces the ordinary anti-steal fence, so it must not be combined with `force_assignee_transfer`. A miss refuses the whole request with `409 precondition_failed`.",
          "maxLength": 255,
          "type": "string"
        },
        "expected_status": {
          "description": "Requires the issue's status to equal this value before the patch. A miss refuses the whole request with `409 precondition_failed`.\n\nUnlike `expected_version` this one is readable: `Issue.status` is on every read of this surface, so a caller can guard a status transition without any token at all.",
          "maxLength": 255,
          "type": "string"
        },
        "expected_version": {
          "description": "Requires the row's revision to equal this value before the patch. A miss refuses the WHOLE request with `409 precondition_failed` and writes nothing \u2014 `ApplyUpdateItem.expected_version`'s contract, on the operation that patches one row.\n\nThe token is the `revision` this operation's own response carries, and the same one `GET /v0/beads/issues/{id}` publishes \u2014 which is where a first guarded write seeds itself, rather than from an unguarded one or from `POST /v0/beads/issues:batchApply`'s `ApplyItemResult.revision`. Compose the next expectation from the value the write ANSWERED with, never from a number the client incremented itself: the token is OPAQUE and compared for equality alone, so it has no predecessor a client can compute.\n\nDECODE IT AS A 64-BIT INTEGER. Live tokens run past 5e17, where an IEEE-754 double's ulp is already 64, so a parser that decodes JSON numbers as doubles \u2014 JavaScript's `JSON.parse`, Go's `any`, Python's `float` \u2014 hands back a value NEAR the token that is not it, and the guard is refused against a row nothing else touched.",
          "type": "integer"
        },
        "force_assignee_transfer": {
          "default": false,
          "description": "Bypasses ONLY a genuine transfer away from a live foreign in-progress owner. Reasserting the exact current assignee is idempotent and needs no force. It requires `patch.assignee` \u2014 a request setting it without one is a `400` \u2014 and it must be false when `expected_assignee` is sent.",
          "type": "boolean"
        },
        "force_close_policy": {
          "default": false,
          "description": "Bypasses ONLY close policy \u2014 the open-children refusal and the live blocker refusal \u2014 for a `patch.status` that crosses into the workspace's done category. It has no effect without such a status change, and it never bypasses validation, the preconditions above, or the assignee fence.",
          "type": "boolean"
        },
        "patch": {
          "$ref": "#/$defs/IssuePatchBody"
        }
      },
      "required": [
        "actor",
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
    "body": {
      "$ref": "#/$defs/UpdateIssueRequest"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "path": {
      "$ref": "#/$defs/Path6"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "body",
    "path",
    "idempotency_key",
    "project"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `NativeResult`; the full envelope schema is the `sinnix://gateway/v2/actions/beads.update` resource and `sinnix-agent-gateway catalog beads.update --schema`.

Examples:

Edit the fields of one issue:

```json
{
  "body": {
    "actor": "example-worker",
    "expected_version": 7,
    "patch": {
      "add_labels": [
        "verified"
      ],
      "append_notes": "Focused regression checks passed."
    }
  },
  "idempotency_key": "example-updateIssue-1",
  "path": {
    "id": "sinnix-abc1"
  },
  "project": {
    "project": "sinnix"
  }
}
```

### `jobs.list`

List queued jobs (pueue tasks) newest first, optionally for one project.

Family: `query`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: job status, job result, job output, phase.

Follow-up actions: `jobs.logs`, `jobs.wait`, `jobs.cancel`, `jobs.retry`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
    "attempt": {
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
    "attempt_limit": {
      "default": 100,
      "maximum": 100,
      "minimum": 1,
      "type": "integer"
    },
    "attempt_offset": {
      "default": 0,
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

Family: `get`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: job log, tail, output, stdout.

Follow-up actions: `jobs.get`, `jobs.wait`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
    "attempt": {
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

The wait runs in a worker thread; cancelling the MCP request abandons it without stopping the job. A task id is a queue position: pass the launch_reference the start returned and the wait follows its job across a reorder, answering with the id it is at now.

Family: `wait`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: wait for job, block, until done.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.cancel`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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

Wait on the job, not the queue position:

```json
{
  "target": {
    "job_id": 41,
    "launch_reference": "sinnix-check-3f9a21c8"
  },
  "timeout_seconds": 60
}
```

### `jobs.cancel`

Pass expected_phase to refuse when the job already moved on. Survivors lists PIDs that outlived the reap.

Family: `operate`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: kill, stop job, abort.

Follow-up actions: `jobs.get`, `jobs.logs`, `jobs.retry`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `operate`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: restart, rerun, requeue.

Follow-up actions: `jobs.wait`, `jobs.get`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

### `jobs.clean`

Refused while the job is still queued or running; cancel it first.

Family: `operate`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: remove job, forget, delete job, prune.

Follow-up actions: `jobs.list`.

Input schema:

```json
{
  "$defs": {
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Output: the response envelope's `data` field is `CleanResult`; the full envelope schema is the `sinnix://gateway/v2/actions/jobs.clean` resource and `sinnix-agent-gateway catalog jobs.clean --schema`.

Examples:

Clean job 41:

```json
{
  "idempotency_key": "clean-41",
  "target": {
    "job_id": 41
  }
}
```

### `operations.run`

Queue one project-declared operation in its declared pool on the root or a worktree.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
    "operation_args": {
      "description": "Validated positional arguments accepted by the declared operation.",
      "items": {
        "type": "string"
      },
      "maxItems": 32,
      "type": "array"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

cwd is confined to the checkout. Default execution is asynchronous. wait=true waits up to wait_timeout_seconds (default 5, maximum 30) on the same job and returns bounded output; a timeout returns a continuation locator without cancelling the job.

Family: `run`. Owner: `systemd-jobs`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "max_output_bytes": {
      "default": 64000,
      "maximum": 262144,
      "minimum": 1,
      "type": "integer"
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    },
    "wait": {
      "default": false,
      "type": "boolean"
    },
    "wait_timeout_seconds": {
      "default": 5,
      "maximum": 30,
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

Output: the response envelope's `data` field is `ShellRunResult`; the full envelope schema is the `sinnix://gateway/v2/actions/shell.run` resource and `sinnix-agent-gateway catalog shell.run --schema`.

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

### `batches.list`

List batch runs newest first, with each worker's stage and task.

Family: `query`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: runs, agentctl batch list, which batches, active runs.

Follow-up actions: `batches.status`, `jobs.logs`, `jobs.wait`.

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
    "limit": {
      "default": 25,
      "maximum": 200,
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
      "description": "Only runs of this project."
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

Output: the response envelope's `data` field is `RunPage`; the full envelope schema is the `sinnix://gateway/v2/actions/batches.list` resource and `sinnix-agent-gateway catalog batches.list --schema`.

Examples:

Recent runs:

```json
{
  "limit": 10
}
```

One project's runs:

```json
{
  "project": {
    "project": "sinnix"
  }
}
```

### `batches.status`

Every id is a pueue task id: pass a worker's or the landing's job_id to jobs.logs, jobs.wait or jobs.cancel, with its job_launch_reference so the call survives a reorder.

Family: `get`. Owner: `systemd-jobs`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: batch status, run status, how is the batch, agentctl batch status.

Follow-up actions: `jobs.logs`, `jobs.wait`, `batches.land`, `batches.resume`.

Input schema:

```json
{
  "$defs": {
    "RunLocator": {
      "additionalProperties": false,
      "description": "A batch run by canonical ref, full run id, or the suffix agentctl accepts.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/runs/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "run_id": {
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
          "description": "Full run id, or its 8-character suffix as `agentctl batch` accepts it."
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
      "$ref": "#/$defs/RunLocator"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `RunView`; the full envelope schema is the `sinnix://gateway/v2/actions/batches.status` resource and `sinnix-agent-gateway catalog batches.status --schema`.

Examples:

By run suffix:

```json
{
  "target": {
    "run_id": "a2c81926"
  }
}
```

By canonical ref:

```json
{
  "target": {
    "ref": "sinnix://projects/sinnix/runs/sinnix-20260906-012123-a2c81926"
  }
}
```

### `batches.start`

backend, model and effort default to the project descriptor's packet defaults. Refused when a bead is claimed or already in a live run. The landing task is queued behind the workers and runs itself.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: dispatch, agentctl batch start, work on bead, start agents.

Follow-up actions: `batches.status`, `jobs.wait`, `jobs.logs`, `jobs.cancel`.

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
      "description": "Defaults to the project descriptor's packet default."
    },
    "beads": {
      "description": "The bead ids to work; each becomes its own worker unless workers groups them.",
      "items": {
        "type": "string"
      },
      "maxItems": 16,
      "minItems": 1,
      "type": "array"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "workers": {
      "anyOf": [
        {
          "items": {
            "items": {
              "type": "string"
            },
            "type": "array"
          },
          "maxItems": 16,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Group the beads into workers; every bead must appear in exactly one group."
    }
  },
  "required": [
    "idempotency_key",
    "project",
    "beads"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `RunStarted`; the full envelope schema is the `sinnix://gateway/v2/actions/batches.start` resource and `sinnix-agent-gateway catalog batches.start --schema`.

Examples:

One bead, one worker:

```json
{
  "beads": [
    "sinnix-abc1"
  ],
  "idempotency_key": "batch-sinnix-abc1",
  "project": {
    "project": "sinnix"
  }
}
```

Two workers, pinned agent:

```json
{
  "backend": "codex",
  "beads": [
    "sinnix-abc1",
    "sinnix-abc2",
    "sinnix-abc3"
  ],
  "effort": "high",
  "idempotency_key": "batch-sinnix-abc1-3",
  "model": "gpt-5.6-terra",
  "project": {
    "project": "sinnix"
  },
  "workers": [
    [
      "sinnix-abc1",
      "sinnix-abc2"
    ],
    [
      "sinnix-abc3"
    ]
  ]
}
```

### `batches.land`

batches.start already queues the first landing behind the workers; this re-queues one after a landing failed. The landing runs as a job, so wait on landing_job_id rather than on this call.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: land, agentctl batch land, publish the batch, merge the run.

Follow-up actions: `jobs.wait`, `jobs.logs`, `batches.status`.

Input schema:

```json
{
  "$defs": {
    "RunLocator": {
      "additionalProperties": false,
      "description": "A batch run by canonical ref, full run id, or the suffix agentctl accepts.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/runs/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "run_id": {
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
          "description": "Full run id, or its 8-character suffix as `agentctl batch` accepts it."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
      "$ref": "#/$defs/RunLocator"
    }
  },
  "required": [
    "idempotency_key",
    "target"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `LandQueued`; the full envelope schema is the `sinnix://gateway/v2/actions/batches.land` resource and `sinnix-agent-gateway catalog batches.land --schema`.

Examples:

Re-run a failed landing:

```json
{
  "idempotency_key": "land-a2c81926",
  "target": {
    "run_id": "a2c81926"
  }
}
```

### `batches.resume`

backend, model and effort default to the worker's own. Refused while the worker's task is still queued or running.

Family: `run`. Owner: `systemd-jobs`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: resume worker, agentctl batch resume, retry the agent.

Follow-up actions: `jobs.wait`, `jobs.logs`, `batches.status`.

Input schema:

```json
{
  "$defs": {
    "RunLocator": {
      "additionalProperties": false,
      "description": "A batch run by canonical ref, full run id, or the suffix agentctl accepts.",
      "properties": {
        "ref": {
          "anyOf": [
            {
              "pattern": "^sinnix://projects/[^/]+/runs/[^/]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "run_id": {
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
          "description": "Full run id, or its 8-character suffix as `agentctl batch` accepts it."
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
      "description": "Defaults to the project descriptor's packet default."
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
      "$ref": "#/$defs/RunLocator"
    },
    "worker": {
      "description": "The worker id, as batches.status names it.",
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "idempotency_key",
    "target",
    "worker"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `ResumeQueued`; the full envelope schema is the `sinnix://gateway/v2/actions/batches.resume` resource and `sinnix-agent-gateway catalog batches.resume --schema`.

Examples:

Resume one worker:

```json
{
  "idempotency_key": "resume-a2c81926-sinnix-abc1",
  "target": {
    "run_id": "a2c81926"
  },
  "worker": "sinnix-abc1"
}
```

### `wait.for`

Conditions: job_terminal, bead_status, bead_revision, unit_state, file_hash, file_exists, capture_freshness, receipt_appearance, terminal_output. A timeout returns the current evidence and a continuation token.

Family: `wait`. Owner: `waits`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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

Family: `events`. Owner: `events`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

The selected owner supplies domain composition, source coverage and partial results. The gateway preserves its product and availability in an immutable observation under snapshot_ref.

Family: `context`. Owner: `context`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Aliases: orient, overview, situation, what is going on, triage, review job, incident.

Follow-up actions: `jobs.list`, `jobs.logs`, `batches.start`, `events.tail`, `wait.for`.

Input schema:

```json
{
  "$defs": {
    "HistoricalSelector": {
      "additionalProperties": false,
      "properties": {
        "revision": {
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
        "timestamp": {
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
        }
      },
      "type": "object"
    },
    "JobLocator": {
      "additionalProperties": false,
      "description": "A queued job by canonical ref or pueue task id, and the job's own name.\n\nA task id is a position in the queue: `pueue switch` exchanges the ids of\ntwo queued tasks, so an id addresses whatever the queue keeps there. The\nlaunch reference every job response carries addresses the job itself, and\na locator that includes one follows its job across a reorder.",
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
        "launch_reference": {
          "anyOf": [
            {
              "maxLength": 512,
              "minLength": 1,
              "pattern": "^[A-Za-z0-9._-]+$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The job's launch reference, as every job response returns it. Include it so the call follows this job if the queue is reordered."
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
    "at": {
      "anyOf": [
        {
          "$ref": "#/$defs/HistoricalSelector"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "baseline": {
      "anyOf": [
        {
          "$ref": "#/$defs/HistoricalSelector"
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
        "incident",
        "campaign.progress",
        "session.orchestration",
        "verification.regression",
        "project.trajectory"
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
    "refresh_id": {
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
    "roots": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "type": "array"
    },
    "session_refs": {
      "items": {
        "type": "string"
      },
      "maxItems": 20,
      "type": "array"
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

Family: `status`. Owner: `desktop`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `desktop`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `operate`. Owner: `desktop`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `catalog`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `run`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `wait`. Owner: `terminals`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `operate`. Owner: `terminals`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `catalog`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `browser`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `operate`. Owner: `browser`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `status`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

### `machine.prepare`

Read the selected target identity and action preconditions without changing it.

Family: `get`. Owner: `ops-reducer`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `machine.operate`.

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
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://(?:jobs|machine/units|processes)/",
      "type": "string"
    }
  },
  "required": [
    "target",
    "request"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `PreparedAction`; the full envelope schema is the `sinnix://gateway/v2/actions/machine.prepare` resource and `sinnix-agent-gateway catalog machine.prepare --schema`.

Examples:

Prepare unit restart:

```json
{
  "request": {
    "action": "restart"
  },
  "target": "sinnix://machine/units/user/example.service"
}
```

### `machine.operate`

expected_target must match the target identity returned by machine.prepare; the reducer receipt is verified against the submitted action and target.

Family: `operate`. Owner: `ops-reducer`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
    "expected_target": {
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
      "description": "Target identity from machine.prepare or the displayed owner observation; also accepted as preconditions.expected_target."
    },
    "idempotency_key": {
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
  "expected_target": {
    "kind": "unit",
    "manager": "user",
    "properties": {
      "ActiveState": "active",
      "InvocationID": "example-invocation"
    },
    "unit": "example.service"
  },
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
  "expected_target": {
    "kind": "unit",
    "manager": "user",
    "properties": {
      "ActiveState": "active",
      "InvocationID": "example-invocation"
    },
    "unit": "example.service"
  },
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

Family: `operate`. Owner: `ops-reducer`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
    "expected_target": {
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
    "idempotency_key": {
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
  "expected_target": {
    "kind": "unit",
    "manager": "user",
    "properties": {
      "ActiveState": "active",
      "InvocationID": "example-invocation"
    },
    "unit": "example.service"
  },
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

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

The reducer path is the attested one and needs expected_target; the direct path is receipted by the gateway audit chain only.

Family: `operate`. Owner: `machine`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
        "expected_target": {
          "additionalProperties": true,
          "description": "Target identity from machine.prepare for this process stop.",
          "type": "object"
        },
        "operation": {
          "const": "stop",
          "default": "stop",
          "type": "string"
        }
      },
      "required": [
        "expected_target"
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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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
    "expected_target": {
      "kind": "process",
      "pid": 4242,
      "start_ticks": 12345
    },
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

Family: `wait`. Owner: `machine`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `status`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `catalog`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Reads require an owner read-only annotation or an exact match to trusted registry selectors. Other requests require mcp.change (operator only). A target using server=sinnix-agent-gateway is routed to the named direct read action, preserving its native content blocks; changes stay direct-only.

Family: `query`. Owner: `mcp-broker`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Invoke an upstream request not admitted as read-only by annotation or trusted registry selectors.

Family: `change`. Owner: `mcp-broker`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Gateway response replay key. Confirmed responses replay unchanged; interrupted effects require owner reconciliation and are never automatically retried.",
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
      "description": "Owner-specific checks; a mismatch fails with precondition_failed. Checks are best effort unless the owner explicitly guarantees an atomic compare and mutation."
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

Family: `catalog`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
    "cursor": {
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

Family: `get`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Read an artifact: text inline with offsets, images as image blocks, other binary as read-only links.

Family: `query`. Owner: `artifacts`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
      "description": "Maximum inline text bytes.",
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
        "text"
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

Family: `query`. Owner: `captures`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `query`. Owner: `captures`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Read indexed session pages or explicit original-source fallback through Polylogue.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

Input schema:

```json
{
  "$defs": {
    "Origin": {
      "description": "Archive source-origin tokens.",
      "enum": [
        "claude-code-session",
        "codex-session",
        "gemini-cli-session",
        "hermes-session",
        "antigravity-session",
        "beads-issue",
        "grok-export",
        "chatgpt-export",
        "claude-ai-export",
        "claude-design-session",
        "aistudio-drive",
        "unknown-export"
      ],
      "type": "string"
    },
    "RawList": {
      "additionalProperties": false,
      "properties": {
        "continuation": {
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
        },
        "limit": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "sessions.raw.list",
          "default": "sessions.raw.list",
          "type": "string"
        },
        "origin": {
          "enum": [
            "claude-code-session",
            "codex-session"
          ],
          "type": "string"
        }
      },
      "required": [
        "origin"
      ],
      "type": "object"
    },
    "RawRead": {
      "additionalProperties": false,
      "properties": {
        "max_bytes": {
          "default": 64000,
          "maximum": 64000,
          "minimum": 4,
          "type": "integer"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "default": "sessions.raw.read",
          "enum": [
            "sessions.raw.read",
            "memory.raw.get"
          ],
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
    "RawSearch": {
      "additionalProperties": false,
      "properties": {
        "continuation": {
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
        },
        "limit": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "sessions.raw.search",
          "default": "sessions.raw.search",
          "type": "string"
        },
        "origin": {
          "enum": [
            "claude-code-session",
            "codex-session"
          ],
          "type": "string"
        },
        "query": {
          "maxLength": 1000,
          "minLength": 1,
          "type": "string"
        },
        "reference": {
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
        },
        "scan_bytes": {
          "default": 8388608,
          "maximum": 8388608,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "origin",
        "query"
      ],
      "type": "object"
    },
    "SessionList": {
      "additionalProperties": false,
      "properties": {
        "continuation": {
          "anyOf": [
            {
              "maxLength": 65536,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expression": {
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
        },
        "limit": {
          "default": 50,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "max_messages": {
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
        "min_messages": {
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
        "min_words": {
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
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "sessions.list",
          "default": "sessions.list",
          "type": "string"
        },
        "origin": {
          "anyOf": [
            {
              "$ref": "#/$defs/Origin"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "repo": {
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
        "since": {
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
        "sort": {
          "anyOf": [
            {
              "enum": [
                "date",
                "tokens",
                "messages",
                "words",
                "longest"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "tag": {
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
        "until": {
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
    "SessionRead": {
      "additionalProperties": false,
      "properties": {
        "continuation": {
          "anyOf": [
            {
              "maxLength": 65536,
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
          "default": 50,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "sessions.read",
          "default": "sessions.read",
          "type": "string"
        },
        "ref": {
          "maxLength": 8192,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "ref"
      ],
      "type": "object"
    },
    "SessionSearch": {
      "additionalProperties": false,
      "properties": {
        "continuation": {
          "anyOf": [
            {
              "maxLength": 65536,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expression": {
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
        },
        "limit": {
          "default": 50,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "max_messages": {
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
        "min_messages": {
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
        "min_words": {
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
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "const": "sessions.search",
          "default": "sessions.search",
          "type": "string"
        },
        "origin": {
          "anyOf": [
            {
              "$ref": "#/$defs/Origin"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "repo": {
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
        "since": {
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
        "sort": {
          "anyOf": [
            {
              "enum": [
                "date",
                "tokens",
                "messages",
                "words",
                "longest"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "tag": {
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
        "until": {
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
          "memory.raw.get": "#/$defs/RawRead",
          "sessions.list": "#/$defs/SessionList",
          "sessions.raw.list": "#/$defs/RawList",
          "sessions.raw.read": "#/$defs/RawRead",
          "sessions.raw.search": "#/$defs/RawSearch",
          "sessions.read": "#/$defs/SessionRead",
          "sessions.search": "#/$defs/SessionSearch"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/SessionList"
        },
        {
          "$ref": "#/$defs/SessionSearch"
        },
        {
          "$ref": "#/$defs/SessionRead"
        },
        {
          "$ref": "#/$defs/RawList"
        },
        {
          "$ref": "#/$defs/RawSearch"
        },
        {
          "$ref": "#/$defs/RawRead"
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

Project sessions:

```json
{
  "request": {
    "operation": "sessions.list",
    "repo": "sinnix"
  }
}
```

### `memory.query`

Search original session sources or read one source object with explicit coverage.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `memory.raw.search`, `sessions.raw.read`.

Input schema:

```json
{
  "$defs": {
    "RawMemorySearch": {
      "additionalProperties": false,
      "properties": {
        "limit": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "operation": {
          "const": "memory.raw.search",
          "default": "memory.raw.search",
          "type": "string"
        },
        "origins": {
          "items": {
            "enum": [
              "claude-code-session",
              "codex-session"
            ],
            "type": "string"
          },
          "maxItems": 2,
          "minItems": 1,
          "type": "array"
        },
        "query": {
          "maxLength": 1000,
          "minLength": 1,
          "type": "string"
        },
        "scan_bytes": {
          "default": 8388608,
          "maximum": 8388608,
          "minimum": 1,
          "type": "integer"
        },
        "source_cursors": {
          "anyOf": [
            {
              "additionalProperties": {
                "anyOf": [
                  {
                    "type": "string"
                  },
                  {
                    "type": "null"
                  }
                ]
              },
              "propertyNames": {
                "enum": [
                  "claude-code-session",
                  "codex-session"
                ]
              },
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "query"
      ],
      "type": "object"
    },
    "RawRead": {
      "additionalProperties": false,
      "properties": {
        "max_bytes": {
          "default": 64000,
          "maximum": 64000,
          "minimum": 4,
          "type": "integer"
        },
        "offset": {
          "default": 0,
          "minimum": 0,
          "type": "integer"
        },
        "operation": {
          "default": "sessions.raw.read",
          "enum": [
            "sessions.raw.read",
            "memory.raw.get"
          ],
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
          "memory.raw.get": "#/$defs/RawRead",
          "memory.raw.search": "#/$defs/RawMemorySearch",
          "sessions.raw.read": "#/$defs/RawRead"
        },
        "propertyName": "operation"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/RawMemorySearch"
        },
        {
          "$ref": "#/$defs/RawRead"
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

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/memory.query` resource and `sinnix-agent-gateway catalog memory.query --schema`.

Examples:

Search original sources:

```json
{
  "request": {
    "operation": "memory.raw.search",
    "query": "screenshot probe"
  }
}
```

### `timeline.query`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

Input schema:

```json
{
  "$defs": {
    "Origin": {
      "description": "Archive source-origin tokens.",
      "enum": [
        "claude-code-session",
        "codex-session",
        "gemini-cli-session",
        "hermes-session",
        "antigravity-session",
        "beads-issue",
        "grok-export",
        "chatgpt-export",
        "claude-ai-export",
        "claude-design-session",
        "aistudio-drive",
        "unknown-export"
      ],
      "type": "string"
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
    "continuation": {
      "anyOf": [
        {
          "maxLength": 65536,
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
          "maxLength": 8192,
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
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "sessions.timeline",
      "default": "sessions.timeline",
      "type": "string"
    },
    "origin": {
      "anyOf": [
        {
          "$ref": "#/$defs/Origin"
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
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "until": {
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
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/timeline.query` resource and `sinnix-agent-gateway catalog timeline.query --schema`.

Examples:

Indexed session events in a time window:

```json
{
  "limit": 50,
  "origin": "codex-session",
  "since": "2026-09-01T00:00:00Z",
  "until": "2026-09-02T00:00:00Z"
}
```

### `sessions.list`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

Input schema:

```json
{
  "$defs": {
    "Origin": {
      "description": "Archive source-origin tokens.",
      "enum": [
        "claude-code-session",
        "codex-session",
        "gemini-cli-session",
        "hermes-session",
        "antigravity-session",
        "beads-issue",
        "grok-export",
        "chatgpt-export",
        "claude-ai-export",
        "claude-design-session",
        "aistudio-drive",
        "unknown-export"
      ],
      "type": "string"
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
    "continuation": {
      "anyOf": [
        {
          "maxLength": 65536,
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
          "maxLength": 8192,
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
      "default": 50,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "max_messages": {
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
    "min_messages": {
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
    "min_words": {
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
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "sessions.list",
      "default": "sessions.list",
      "type": "string"
    },
    "origin": {
      "anyOf": [
        {
          "$ref": "#/$defs/Origin"
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
    "repo": {
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
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "sort": {
      "anyOf": [
        {
          "enum": [
            "date",
            "tokens",
            "messages",
            "words",
            "longest"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "tag": {
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
    "until": {
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
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.list` resource and `sinnix-agent-gateway catalog sessions.list --schema`.

Examples:

Recent indexed project sessions:

```json
{
  "limit": 20,
  "repo": "sinnix",
  "sort": "date"
}
```

### `sessions.search`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

Input schema:

```json
{
  "$defs": {
    "Origin": {
      "description": "Archive source-origin tokens.",
      "enum": [
        "claude-code-session",
        "codex-session",
        "gemini-cli-session",
        "hermes-session",
        "antigravity-session",
        "beads-issue",
        "grok-export",
        "chatgpt-export",
        "claude-ai-export",
        "claude-design-session",
        "aistudio-drive",
        "unknown-export"
      ],
      "type": "string"
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
    "continuation": {
      "anyOf": [
        {
          "maxLength": 65536,
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
          "maxLength": 8192,
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
      "default": 50,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "max_messages": {
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
    "min_messages": {
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
    "min_words": {
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
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "sessions.search",
      "default": "sessions.search",
      "type": "string"
    },
    "origin": {
      "anyOf": [
        {
          "$ref": "#/$defs/Origin"
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
    "repo": {
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
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "sort": {
      "anyOf": [
        {
          "enum": [
            "date",
            "tokens",
            "messages",
            "words",
            "longest"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "tag": {
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
    "until": {
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
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.search` resource and `sinnix-agent-gateway catalog sessions.search --schema`.

Examples:

Find sessions discussing pagination:

```json
{
  "expression": "pagination",
  "limit": 20,
  "repo": "sinnix"
}
```

### `sessions.read`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "continuation": {
      "anyOf": [
        {
          "maxLength": 65536,
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
      "default": 50,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "sessions.read",
      "default": "sessions.read",
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
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
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
    }
  },
  "required": [
    "ref"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.read` resource and `sinnix-agent-gateway catalog sessions.read --schema`.

Examples:

Read an indexed session message page:

```json
{
  "limit": 25,
  "offset": 0,
  "ref": "session:example-session"
}
```

### `sessions.raw.list`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "continuation": {
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
    "operation": {
      "const": "sessions.raw.list",
      "default": "sessions.raw.list",
      "type": "string"
    },
    "origin": {
      "enum": [
        "claude-code-session",
        "codex-session"
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
    "origin"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.raw.list` resource and `sinnix-agent-gateway catalog sessions.raw.list --schema`.

Examples:

List original Codex session sources:

```json
{
  "limit": 20,
  "origin": "codex-session"
}
```

### `sessions.raw.search`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "continuation": {
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
    "operation": {
      "const": "sessions.raw.search",
      "default": "sessions.raw.search",
      "type": "string"
    },
    "origin": {
      "enum": [
        "claude-code-session",
        "codex-session"
      ],
      "type": "string"
    },
    "query": {
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
    "reference": {
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
    "scan_bytes": {
      "default": 8388608,
      "maximum": 8388608,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "origin",
    "query"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.raw.search` resource and `sinnix-agent-gateway catalog sessions.raw.search --schema`.

Examples:

Search original Claude Code transcripts:

```json
{
  "limit": 20,
  "origin": "claude-code-session",
  "query": "pagination",
  "scan_bytes": 1048576
}
```

### `sessions.raw.read`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "max_bytes": {
      "default": 64000,
      "maximum": 64000,
      "minimum": 4,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "sessions.raw.read",
      "default": "sessions.raw.read",
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
    "reference": {
      "maxLength": 8192,
      "minLength": 1,
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
    }
  },
  "required": [
    "reference"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.raw.read` resource and `sinnix-agent-gateway catalog sessions.raw.read --schema`.

Examples:

Read a bounded original transcript page:

```json
{
  "max_bytes": 16000,
  "offset": 0,
  "reference": "codex:2026/09/01/example-session.jsonl"
}
```

### `sessions.raw.timeline`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "continuation": {
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
    "operation": {
      "const": "sessions.raw.timeline",
      "default": "sessions.raw.timeline",
      "type": "string"
    },
    "origins": {
      "items": {
        "enum": [
          "claude-code-session",
          "codex-session"
        ],
        "type": "string"
      },
      "maxItems": 2,
      "minItems": 1,
      "type": "array"
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
    "scan_bytes": {
      "default": 8388608,
      "maximum": 8388608,
      "minimum": 1,
      "type": "integer"
    },
    "since": {
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
    "until": {
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
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.raw.timeline` resource and `sinnix-agent-gateway catalog sessions.raw.timeline --schema`.

Examples:

Original sources modified in a time window:

```json
{
  "limit": 20,
  "origins": [
    "claude-code-session",
    "codex-session"
  ],
  "since": "2026-09-01T00:00:00Z",
  "until": "2026-09-02T00:00:00Z"
}
```

### `memory.raw.get`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "max_bytes": {
      "default": 64000,
      "maximum": 64000,
      "minimum": 4,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "operation": {
      "const": "memory.raw.get",
      "default": "memory.raw.get",
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
    "reference": {
      "maxLength": 8192,
      "minLength": 1,
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
    }
  },
  "required": [
    "reference"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/memory.raw.get` resource and `sinnix-agent-gateway catalog memory.raw.get --schema`.

Examples:

Read one original memory source:

```json
{
  "max_bytes": 16000,
  "offset": 0,
  "reference": "claude-code:example-project/example-session.jsonl"
}
```

### `memory.raw.search`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "limit": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "operation": {
      "const": "memory.raw.search",
      "default": "memory.raw.search",
      "type": "string"
    },
    "origins": {
      "items": {
        "enum": [
          "claude-code-session",
          "codex-session"
        ],
        "type": "string"
      },
      "maxItems": 2,
      "minItems": 1,
      "type": "array"
    },
    "query": {
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
    "scan_bytes": {
      "default": 8388608,
      "maximum": 8388608,
      "minimum": 1,
      "type": "integer"
    },
    "source_cursors": {
      "anyOf": [
        {
          "additionalProperties": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ]
          },
          "propertyNames": {
            "enum": [
              "claude-code-session",
              "codex-session"
            ]
          },
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "query"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/memory.raw.search` resource and `sinnix-agent-gateway catalog memory.raw.search --schema`.

Examples:

Find pagination notes across original sources:

```json
{
  "limit": 20,
  "origins": [
    "claude-code-session",
    "codex-session"
  ],
  "query": "pagination"
}
```

### `sessions.resume`

Input fields are generated from the Polylogue operation contract. Owner coverage, native references, pagination and errors are retained in owner_product.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.read`, `sessions.search`, `timeline.query`.

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
    "cwd": {
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
    "operation": {
      "const": "context.resume",
      "default": "context.resume",
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
    "recent_files": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "type": "array"
    },
    "related_limit": {
      "default": 5,
      "maximum": 20,
      "minimum": 1,
      "type": "integer"
    },
    "repo_path": {
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
    "session_id": {
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
}
```

Output: the response envelope's `data` field is `SessionsResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.resume` resource and `sinnix-agent-gateway catalog sessions.resume --schema`.

Examples:

Resume work in a checkout:

```json
{
  "recent_files": [
    "README.md"
  ],
  "related_limit": 3,
  "repo_path": "/realm/project/sinnix"
}
```

### `campaign.progress`

Task closure, verified delivery and acceptance remain separate. Missing evidence is unknown; bounded closure cannot establish an exact denominator. Historical task state is read at its resolved owner revision.

Family: `query`. Owner: `lynchpin`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `beads.query`, `beads.get`, `context.compose`.

Input schema:

```json
{
  "$defs": {
    "HistoricalSelector": {
      "additionalProperties": false,
      "properties": {
        "revision": {
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
        "timestamp": {
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
    "at": {
      "anyOf": [
        {
          "$ref": "#/$defs/HistoricalSelector"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "baseline": {
      "anyOf": [
        {
          "$ref": "#/$defs/HistoricalSelector"
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
    "direction": {
      "default": "prerequisites",
      "enum": [
        "prerequisites",
        "dependents"
      ],
      "type": "string"
    },
    "max_depth": {
      "default": 50,
      "maximum": 100,
      "minimum": 1,
      "type": "integer"
    },
    "max_nodes": {
      "default": 500,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
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
    "refresh_id": {
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
    "relation": {
      "default": "blocks",
      "enum": [
        "blocks",
        "parent-child"
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
    "roots": {
      "items": {
        "type": "string"
      },
      "maxItems": 100,
      "minItems": 1,
      "type": "array"
    }
  },
  "required": [
    "project",
    "roots"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `CampaignResult`; the full envelope schema is the `sinnix://gateway/v2/actions/campaign.progress` resource and `sinnix-agent-gateway catalog campaign.progress --schema`.

Examples:

Campaign evidence:

```json
{
  "project": {
    "project": "sinnix"
  },
  "roots": [
    "sinnix-1"
  ]
}
```

### `sessions.orchestration`

Native parent, model and token fields remain unknown when absent from stored evidence. Each owner product retains its coverage, provenance and ingestion watermark.

Family: `query`. Owner: `polylogue`. Principals: `observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

Follow-up actions: `sessions.query`, `context.compose`.

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
    "session_refs": {
      "items": {
        "type": "string"
      },
      "maxItems": 20,
      "minItems": 1,
      "type": "array"
    }
  },
  "required": [
    "session_refs"
  ],
  "type": "object"
}
```

Output: the response envelope's `data` field is `OrchestrationResult`; the full envelope schema is the `sinnix://gateway/v2/actions/sessions.orchestration` resource and `sinnix-agent-gateway catalog sessions.orchestration --schema`.

Examples:

Session orchestration:

```json
{
  "session_refs": [
    "session:example"
  ]
}
```

### `audit.verify`

Verify the tamper-evident audit hash chain end to end.

Family: `status`. Owner: `audit`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `audit`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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

Family: `get`. Owner: `results`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
          "pattern": "^sinnix://(?:results|contexts)/[^/]{1,128}$",
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

Family: `catalog`. Owner: `capability-index`. Principals: `agent-control, observer, operator`. Typed failures: `conflict, deadline, idempotency_conflict, indeterminate, invalid_request, not_found, owner_failed, partial_completion, policy_denied, precondition_failed, response_bound, source_changed, stale_cursor, unavailable, unsupported_capability`.

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
