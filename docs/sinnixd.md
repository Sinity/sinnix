# Sinnixd

`sinnixd` is the host-local runtime behind `agentctl` and the future execution-facing Sinnix MCP routes. It uses a mode-0600 Unix socket at `$XDG_RUNTIME_DIR/sinnixd.sock`. MCP remains a stateless policy frontend. Systemd, Git, project adapters, and task backends remain authoritative for their own state.

## Current vertical slice

The deployed slice discovers explicit project adapters and can launch only their declared operations:

```text
agentctl status
agentctl project list
agentctl project get sinnix
agentctl project operations sinnix
agentctl workspace list --project sinnix
agentctl workspace create sinnix my-lane --branch feature/my-lane
agentctl workspace adopt sinnix worktree-0123456789abcdef adopted-lane
agentctl workspace get <workspace-id>
agentctl workspace checkpoint <workspace-id>
agentctl workspace restore <workspace-id> <checkpoint-id>
agentctl workspace recover <workspace-id> <checkpoint-id>
agentctl workspace stack <parent-workspace-id> child-lane --branch feature/child
agentctl workspace restack <child-workspace-id>
agentctl workspace publish <workspace-id> --job <job-id> --title 'Review title' --body 'Review body'
agentctl workspace review-status <workspace-id>
agentctl workspace land <workspace-id> --job <job-id>
agentctl workspace finish <workspace-id>
agentctl workspace dispose <workspace-id>
agentctl workspace reap <workspace-id>
agentctl job start sinnix lint
agentctl job start sinnix sinex_cache_prebuild
agentctl job start sinex check_default --parameters-json '{"full":true,"package":["sinexd","xtask"]}'
agentctl job start polylogue verify_quick --workspace <workspace-id>
agentctl job get <job-id>
agentctl job list
agentctl job wait <job-id>
agentctl job logs <job-id> --max-bytes 64000
agentctl job result <job-id> --max-bytes 64000
agentctl job cancel <job-id>
agentctl shell --project sinnix --checkout default --cwd . -- printf 'harmless command\n'
agentctl agent --project sinnix --checkout default --prompt-file ./prompt.md --backend codex --model gpt-5.6-terra --effort high
agentctl task create sinnix 'Follow-up title' --description 'Bounded task description.' --type task --priority 2 --label area:agentctl --parent sinnix-oy37 --dependency depends-on:sinnix-oy37.9 --request-id 2d8f1e3a-61d0-4d3c-bb9a-9e8baa3a5cac
```

The service passes a declarative, non-empty `sinnix.services.sinnixd.projectRoots` list as repeated `--project-root` arguments. It defaults to the registered Sinnix project entries. Sinnixd loads only those `.agentctl/project.toml` adapters and does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata. A descriptor with a `[workspace]` is agent-capable and must declare non-empty shell-free argv lists for both `environment.command` and `environment.preflight`; the latter runs inside the former from the revalidated checkout before any backend starts. `agentctl project get <id>` publishes that capability and both public argv lists.

The environment contract gate evaluates the configured `sinnix.services.sinnixd.projectRoots` and runs `sinnixd-project-environment-check` against the real descriptors. It reports every missing or invalid required declaration and stops before a host configuration is built or activated. The gate runs for `nix run .#switch`, `nix run .#boot`, `nix run .#test-system`, and the devshell `switch`, `boot`, and `test-system` commands. `test-vm` remains separate because it only builds a guest image and does not activate the live host. Roll out descriptor commits before this Sinnix commit. The minimum declaration for every external agent-capable descriptor is `preflight = ["true"]` under `[environment]`; a project may use a stronger cheap project-native readiness argv instead. The current external prerequisites are Polylogue, Sinex, and Lynchpin, and all three descriptors must satisfy this contract before any gated command is run.

The optional `sinnixd-reactor` user service is the model-free owner of campaign mechanics. It consumes the append-only completion-event spool from a durable cursor, atomically maintains the versioned `campaign-board.json`, closes merged Beads only from a decision-time receipt, and marks successful Polylogue agent lanes `review_ready`. It also scans terminal Polylogue `verify_all` job records and stores a consecutive-failure rollup in `corpus_health`. After three failures by default, it emits one `corpus-health-alert` event for that failure streak, including each job's terminal phase and typed cancellation or error evidence. A later success clears the alert state. Its registered keeper reaction emits one actionable `keeper` event per pending action and exponentially backs off repeated emissions. Explicit requests for `verify_all` or rehearsal operations stay in the board until the configured active-lane gate clears, then use the declared `job start` route. It does not review, harvest, or select work; those remain fresh-context harvester and strategist responsibilities.

`job start` accepts a project ID, one declared operation name, an optional workspace binding, and an optional JSON parameters object. It never accepts an arbitrary command. Its optional workspace binding launches in that registered checkout and durably records the checkout ID and exact starting HEAD, so later publication can reject stale verification. Declared operations and internal synthetic foreground commands construct the same durable generic-job spec, record, transient user `.service` launch, log artifact, reconciliation, wait, and cancellation route. A descriptor may set a bounded `timeout_seconds`; that becomes the transient service limit, rather than a caller-controlled duration. The typed attested-agent contract also accepts an optional validated Beads binding from the gateway. It is public durable provenance, not prompt material: canonical bead/project/checkout refs, launch task revision and etag, optional claim receipt, request ID, and display-only work item. The only additional public starts are the constrained typed contracts below.

An operation may also declare `schedule = "OnCalendar expression"`. Sinnixd registers each such operation as a persistent transient user-manager timer and reconciles the timer set from a durable schedule map at daemon startup, so a daemon restart does not lose a calendar firing. The timer only invokes the daemon's schedule-fire route; Sinnixd validates the declared schedule and submits an ordinary admitted declared-operation job. Its durable dimensions record the schedule ID, expression, timer unit, and `systemd-timer` trigger, so scheduled work has the same records, events, retention, and admission path as an explicit start. Scheduled operations cannot require parameters.

## Declared development-service leases

A declared operation may add one closed `[operations.<name>.service]` contract for a bounded development service. It carries readiness metadata (`none` or `project-command`), `lifetime = "job"`, and one through eight named loopback port slots. Each slot declares one `PORT` or `*_PORT` environment-variable name and an inclusive 1024 through 65535 range of at most 256 ports. The descriptor is static. `job start` accepts no port, environment, readiness, lifetime, or service-command arguments.

```toml
[operations.dev_server]
description = "Run the project development server"
exec = ["just", "dev"]
pool = "interactive"
result = "exit"
cache = "none"

[operations.dev_server.service]
readiness = "project-command"
lifetime = "job"

[operations.dev_server.service.ports.http]
environment = "DEV_SERVER_PORT"
range = [41000, 41031]
```

Sinnixd allocates distinct available ports under the durable generic-job ID, injects only the declared slot variables, and launches through the existing transient user-service path. The job record and its `job start`, `job get`, `job list`, and Gateway projections expose only bounded public lease metadata: lease ID, `127.0.0.1`, readiness and lifetime labels, slot names, environment names, allocated ports, and active or released state. Raw argv, environment values outside the allocated ports, prompts, and secrets remain absent from durable public state.

The generic job record, private launch input, and lease reservation are published before systemd launch. A failed input publication terminalizes the record before launch. Startup treats an incomplete private input as failed only after systemd proves the unit absent, otherwise it preserves the record for safe reconciliation. Allocation derives occupied ports from valid nonterminal records and unreleased terminal records as well as lease files. A terminal record retains its reservation until systemd proves the unit absent, then recovery records its release and reclaims it. An unavailable systemd observation retains the lease. The project command owns readiness and convergence. Sinnixd does not add probes, PID tracking, archive semantics, or a second scheduler.

## Declared-operation timeout contract

An operation may declare `timeout_seconds` as a positive integer. Omission keeps the 3,600-second default. Declared operations may use at most 28,800 seconds (eight hours), which accommodates finite full suites and long-running source or automaton batches while still providing a fixed systemd deadline. Descriptor parsing rejects booleans, non-integers, zero, negative values, and values above that maximum. The catalog, job response, durable job spec, recovery path, and `RuntimeMaxSec` all carry this one descriptor-owned value. Gateway and MCP clients receive the same catalog and job metadata; they do not accept a second timeout override.

The longer maximum applies only to `declared-operation` jobs. `agentctl shell`, `agentctl agent`, internal foreground commands, and source-scoped owner adapters retain their existing bounds. In particular, shell and attested-agent jobs remain capped at 3,600 seconds, and the contract runner validates that identity before execution. Declared operations execute through the fixed capture launcher rather than that typed-job runner, so extending a suite cannot widen arbitrary command authority.

## Declared-operation parameters and results

Operation parameters are descriptor-owned. The server accepts only parameter names and types declared under that operation, converts them to a fixed argument vector without a shell, and rejects unknown fields, malformed values, missing bounds, and values beyond those bounds. There is no caller-controlled argv, environment, working directory, or timeout on this route.

Each parameter declares exactly one mapping: a long `flag`, or a required `position`. Positional parameters are scalar `string`, `enum`, or `integer` values. They must set `required = true`; optional, list, and boolean positional declarations are invalid. Positions are positive, unique, and contiguous from `1`, so descriptor table order can never choose a positional argv order. Flag parameters retain the existing optional behavior and their descriptor-table order controls only their flag order, regardless of JSON object ordering. The server never invokes a shell.

```toml
[operations.sinex_all_sources]
description = "Run Sinex's all-sources foreground operation"
exec = ["xtask", "run", "all-sources"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.sinex_all_sources.parameters.instance_id]
type = "string"
flag = "--instance-id"
max_length = 128
grammar = "safe-token"

[operations.sinex_all_sources.parameters.reconcile]
type = "bool"
flag = "--reconcile"

[operations.sinex_all_sources.parameters.service_name]
type = "string"
flag = "--service-name"
max_length = 128
grammar = "safe-token"

[operations.sinex_all_sources.parameters.include_default_excluded]
type = "bool"
flag = "--include-default-excluded"

[operations.verify_closure]
description = "Verify closure work for one Bead"
exec = ["xtask", "verify", "closure"]
pool = "normal"
result = "exit"
cache = "tree+environment"

[operations.verify_closure.parameters.bead_id]
type = "string"
position = 1
required = true
max_length = 128
grammar = "safe-token"

[operations.verify_closure.parameters.json]
type = "bool"
flag = "--json"

[operations.verify_closure.parameters.dry_run]
type = "bool"
flag = "--dry-run"
```

`bool` emits its flag only when true. Flag-mapped `string`, `enum`, and `integer` values emit one flag-value pair. `string-list` and `enum-list` require non-empty arrays, deduplicate and sort their values, then repeat the fixed flag once per canonical value. False booleans and absent flag parameters emit nothing. A required positional scalar emits exactly one argv item. Derived argv is always `exec`, then positional values in ascending `position`, then present flags in descriptor-table order. Dependencies run with an empty parameter object, so an operation with required parameters cannot be a dependency target or declare dependencies of its own. Scalar strings require `max_length`; the optional `grammar` selects one safe grammar, with `safe-token` as the default. The supported grammars are `safe-token` (`[A-Za-z0-9][A-Za-z0-9._:+@=-]*`), `identifier` (`[A-Za-z_][A-Za-z0-9_]*`), `package-name` (`[A-Za-z0-9][A-Za-z0-9_-]*`), and `duration` (`[1-9][0-9]{0,8}(ms|s|m|h)`). Arbitrary descriptor regexes are not accepted. Enum values must be a non-empty, unique safe-token set. Integers require inclusive `min` and `max` within signed 32-bit range. Lists require `max_items` from 1 through 32; strings and enum values are limited to 128 characters, and declared `max_length` must be from 1 through 128. An operation has at most 16 parameters and an enum has at most 64 values. Unknown descriptor fields, malformed definitions, duplicate flags or positional positions, gapped positions, booleans supplied as integers, unsafe strings, empty lists, and out-of-range values are rejected before launch.

For the all-sources example, `{"instance_id":"operator-source-driver-browser.history-3","reconcile":true,"service_name":"source-driver-browser.history-3","include_default_excluded":true}` produces `xtask run all-sources --instance-id operator-source-driver-browser.history-3 --reconcile --service-name source-driver-browser.history-3 --include-default-excluded` before the declared environment prefix. These names match Sinex's source-binding identities, whose defaults are `source-driver-<source_id>-<instance_idx>`. If a project declares the shown closure operation, `{"bead_id":"sinex-a1b2","json":true,"dry_run":true}` produces `xtask verify closure sinex-a1b2 --json --dry-run`; the current Sinex descriptor does not publish that operation. The normalized non-default object, including required positional values, is encoded as sorted compact JSON and SHA-256 hashed. Each declared job record and `job start`, `job get`, and `job list` response exposes only `parameters.digest`, a lowercase 64-hex digest. Raw parameter values are absent from public durable job metadata. The private launch intent may temporarily retain the derived argv and environment while a job needs recovery. Operations with no `[operations.<name>.parameters]` table remain fixed and reject every non-empty parameters object.

Descriptor `result` is executable contract data. `exit` remains log-only. `json` and `pytest` allocate a bounded result artifact, capture stdout separately from the combined log, and require one UTF-8 JSON object. `agentctl job result` returns that object as typed `value`; malformed, injected trailing output, arrays, and overflowed artifacts are rejected. The record persists `result_kind`, and the result artifact metadata exposes its kind and bound. Polylogue currently declares `verify_affected` and `verify_all` as `pytest`, so their JSON receipts are consumable through this route. Its `verify_quick` still declares `exit`; its descriptor must change to `json` or `pytest` before its receipt is consumable, and this repository does not make that cross-repository declaration change.

## Canonical task authority

Every registered project has one standalone Beads authority workspace at `$SINNIXD_TASK_STATE_ROOT/<project>`, defaulting to `/realm/state/tasks/<project>`, with its physical database at `<project>/.beads/dolt`. Sinnixd sets `BEADS_DIR` to that canonical `.beads` directory for every task mutation, reconciliation, and snapshot while retaining the registered checkout as the command CWD and project identity. Task reads (`list`/`get`) are deliberately not proxied: read task state through the `bd` CLI directly (the checkout's `.beads/redirect` reaches the same authority); the daemon owns only mutation identity, journaling, reconcile, and the authority-bound snapshot. It never uses `--db`: Beads 1.1 treats an existing path there as a legacy embedded workspace and rejects it. The checkout's `.beads/redirect` points to the same authority for native `bd` clients and worktrees; neither its branch nor `.beads/issues.jsonl` participates in task authority selection. `task.snapshot` remains a read-only export from the canonical workspace. Historical snapshot consumers are a separate product concern and never become live task authority.

Mutations are first recorded under `<project>/sinnixd-task-mutations`. Each record is bounded, atomically replaced, fsynced, and has one explicit state: `pending`, `dispatching`, `applied`, or `failed`. Public receipts contain the project, task, operation, a SHA-256 idempotency digest, attempt count, a bounded result digest, and a typed failure code. They never contain note text, close reasons, backend stderr, or raw request IDs. A mode-0600 private intent stores the fixed Beads argv only while a pending mutation needs replay; it is removed after a confirmed application. The journal is capped at 1,024 records per project, so new mutations fail visibly instead of silently losing idempotency evidence.

An unavailable Beads launch leaves a mutation `pending` and returns that pending receipt. It is not a completed task. `task.reconcile` schedules a fixed, project-serialized runner that replays pending intents and then runs `bd sync --no-adopt`; both use the same owner lock as direct mutations. A crash after durable `dispatching` state is `failed` with `OWNER_UNAVAILABLE` outcome-unknown evidence, rather than issuing the command again. This is deliberately conservative: reconciliation only retries work that never reached a backend process. The authority root, not the Git checkout, contains the journal and Beads database, so replay does not create task-only Git changes.

`task.create` requires a typed title, description, issue type, priority, labels list, optional parent task ID, and typed dependency relations (`relation:task-id` from the CLI). Sinnixd compiles those values into one fixed `bd create` command with `--parent` and `--deps`; the backend owns graph validation and applies it as the one canonical mutation. A successful response carries `task_ref` in the shared `sinnix://projects/<project>/beads/<id>` form plus bounded owner evidence containing only the journal state, attempt count, result digest and byte count, created ID, and failure code. No title or description enters the public journal.

`task.complete` requires both `--request-id` and `--merge-sha`. Its durable identity is `(project, task, merge SHA)`, not the request ID, so retries with a new request ID do not call Beads a second time. Reusing that merge SHA for the same project and task with different completion arguments is rejected. Other mutation kinds use their stable request ID as their durable identity.

An authority remains unavailable until `<project>/authority.json` attests one completed cutover. The receipt binds the project ID, canonical and source database paths, equal SHA-256 digests of source and destination exports, and equal issue-row counts. The source `.beads/dolt` must be absent and the source `.beads/redirect` must resolve to the canonical `.beads` directory. Sinnixd rejects a missing or malformed receipt, unequal verification evidence, a missing canonical database, or an ambiguous source. This makes interrupted bootstrap and dual live authorities fail closed.

The migration is an operator maintenance action and must run once per project. Stop Sinnixd first, ensure no direct `bd` client can write the project, and confirm the source Dolt server is stopped. The following is the exact Sinnix cutover; substitute the project ID and root for Polylogue and Sinex. It retains the original database as `legacy-dolt-pre-cutover` and does not delete either copy.

```bash
set -euo pipefail
project_id=sinnix
project_root=/realm/project/sinnix
task_state_root=/realm/state/tasks
authority_root="$task_state_root/$project_id"
authority_beads="$authority_root/.beads"
source_database="$project_root/.beads/dolt"
staging_database="$authority_beads/dolt.staging"
canonical_database="$authority_beads/dolt"
scratch_dir="$(mktemp -d "/realm/tmp/work/task-cutover.${project_id}.XXXXXX")"

systemctl --user stop sinnixd.service
bd --directory "$project_root" dolt stop
test "$(bd --directory "$project_root" dolt status --json | jq -r .running)" = false
test -d "$source_database"
test ! -e "$authority_root"
install -d -m 0700 "$authority_root" "$authority_beads"

bd --directory "$project_root" --readonly export >"$scratch_dir/source.jsonl"
source_rows="$(bd --directory "$project_root" --readonly sql 'SELECT COUNT(*) AS row_count FROM issues' --json | jq -er '.[0].row_count')"
bd --directory "$project_root" dolt stop
test "$(bd --directory "$project_root" dolt status --json | jq -r .running)" = false

install -m 0600 "$project_root/.beads/config.yaml" "$authority_beads/config.yaml"
install -m 0600 "$project_root/.beads/metadata.json" "$authority_beads/metadata.json"
rsync -a --exclude='*/.dolt/git-remote-cache/' -- "$source_database/" "$staging_database/"
diff --recursive --brief --no-dereference --exclude=git-remote-cache "$source_database" "$staging_database"

mv "$staging_database" "$canonical_database"
mv "$source_database" "$authority_root/legacy-dolt-pre-cutover"
printf '1.1.0\n' > "$authority_beads/.local_version"
printf '%s\n' "$authority_beads" > "$project_root/.beads/redirect"
bd --directory "$authority_root" dolt start
bd --directory "$authority_root" --readonly export >"$scratch_dir/destination.jsonl"
destination_rows="$(bd --directory "$authority_root" --readonly sql 'SELECT COUNT(*) AS row_count FROM issues' --json | jq -er '.[0].row_count')"
bd --directory "$authority_root" dolt stop
cmp "$scratch_dir/source.jsonl" "$scratch_dir/destination.jsonl"
test "$source_rows" -eq "$destination_rows"
source_digest="sha256:$(sha256sum "$scratch_dir/source.jsonl" | awk '{print $1}')"
destination_digest="sha256:$(sha256sum "$scratch_dir/destination.jsonl" | awk '{print $1}')"
test "$source_digest" = "$destination_digest"
receipt_tmp="$authority_root/.authority.json.tmp"
jq -n \
  --arg project_id "$project_id" \
  --arg database "$canonical_database" \
  --arg source_database "$source_database" \
  --arg source_digest "$source_digest" \
  --arg destination_digest "$destination_digest" \
  --argjson source_rows "$source_rows" \
  --argjson destination_rows "$destination_rows" \
  '{schema: 1, project_id: $project_id, database: $database, source_database: $source_database, verification: {source_export_sha256: $source_digest, destination_export_sha256: $destination_digest, source_rows: $source_rows, destination_rows: $destination_rows}}' \
  >"$receipt_tmp"
chmod 0600 "$receipt_tmp"
mv "$receipt_tmp" "$authority_root/authority.json"
test ! -e "$source_database"
test "$(cat "$project_root/.beads/redirect")" = "$authority_beads"
systemctl --user start sinnixd.service
```

If any verification or cutover command fails, leave Sinnixd stopped. Before the two `mv` commands, the source remains authoritative and the incomplete destination has no receipt. After those commands, either finish the symlink and receipt or move `legacy-dolt-pre-cutover` back to `.beads/dolt`; Sinnixd will refuse task operations until one state is unambiguous.

## Typed shell and agent contracts

`agentctl shell` is an explicit operator capability. It accepts an exact argv, a relative working directory inside an explicit registered Git checkout, a timeout, and only the `exit-status` result kind. `agentctl agent` is an explicit `agent-control` capability. It accepts a private prompt file plus a declared backend, model, effort, credential profile, timeout, and only the `last-message` result kind. Observer and local-default principals cannot use either route.

Both routes use the same UUID job ID, transient user service, cancellation, reconciliation, `job get/list/logs/result/wait`, and bounded artifact readers as declared operations. Their durable public record contains the principal, job kind, canonical project and checkout identity, redacted argv digest or prompt digest, and bounded artifact references. It never stores raw shell argv arguments after launch, prompt text, environment values, or credentials.

Delivery is a precondition of `workspace.publish` and `workspace.land`, not a caller-fed completion route. Ordinary delivery reads the exact-head declared verification job through `job.result`. Packet delivery additionally names the Beads-bound attested-agent job with `--packet-job`. The declared verification job receives the same immutable Beads identity and write-scope binding at dispatch; each job record independently freezes its checkout head, and the contract runner seals the worker's structured report to the Git head observed when the runner exits. Delivery requires the bindings to match, the later semantic verifier to succeed at that same final head, snapshots the packet's initial-to-final Git range, and checks the complete current base-to-head publication diff against the Beads-owned scope. It rejects dirty, divergent, stale, or out-of-scope publication work and repeats the complete precondition after push and after review inspection. The worker report can only tighten acceptance through bounded anti-vacuity, unresolved-work, delegation-visibility, exact deletion evidence, and evidence-only fields. Git owns paths, commits, and heads; the project verifier owns semantic success; GitHub branch protection owns required review state.

Typed jobs accept no environment overlay. The daemon creates the `env -i` environment from the declared project environment and fixed `SINNIXD_*` identity fields. Immediately before execution, the contract runner verifies those fields, rechecks the exact registered project, canonical worktree root, common Git directory, porcelain worktree membership, and recorded HEAD. A changed, missing, symlinked, or spoofed identity fails closed. Every attested agent runs its mandatory environment `preflight` from the revalidated checkout, then invokes the native backend through the same descriptor-owned `environment.command`. A missing, failed, unavailable, or 30-second `agent-preflight-timeout` preflight terminates the typed job before backend implementation starts and retains an actionable runner error in the bounded log. Attested-agent private inputs use schema v2; v1 records fail closed as stale contract input and must be relaunched. The shared transient user service remains the sole process, cgroup, timeout, and cancellation authority. Private launch inputs are mode 0600, removed before shell execution, and removed after handoff or every terminal lifecycle outcome, including confirmed launch failure. Native private logs are removed after handoff; only the bounded shared log and result artifacts remain addressable.

Each record is stored under `$XDG_STATE_HOME/sinnixd` and contains safe operation identity, environment key names, and its bounded-read log artifact path. Record replacement fsyncs the containing directory, and newly created state directories are synchronized before they contain durable evidence. The `sinnixd-job-*.service` dynamic runtime surface and its record capture lane are declared with the daemon, rather than with any MCP frontend. Internal foreground argv is launch-only: the durable record has only a SHA-256 digest and constant display metadata, never raw argv or environment values. The systemd-launched capture helper drains output but writes at most 1 MiB per job; it creates its overflow marker with the first discarded byte, so a live log reader can see truncation before the producer exits. It also fsyncs a completion marker only after the captured process exits successfully and all bounded outputs are durable. It does not own a PID, process state, queue, task, workspace, or retry policy. A job ID deterministically derives its unit name. Every `systemd-run` and `systemctl` call has a short finite bound. `job.wait` caps each reconciliation call to its remaining deadline, so a stalled user manager cannot hold a wait or reserved control worker indefinitely. After a daemon restart, `get`, `list`, `wait`, and `cancel` reload the record and reconcile with the user manager. If `systemd-run` loses its reply but `show` finds the transient unit, `job start` returns the reconciled systemd state. If both the launch reply and its first reconciliation are unavailable, `job start` returns a durable nonterminal `launch-unknown` result with the stable job ID and unit. Later `get`, `wait`, and `cancel` use that same identity to reconcile it. A confirmed absent launch becomes terminal `launch-failed`. A confirmed missing unit after launch remains terminal `missing`; an unreachable or timed-out systemd observation is durable nonterminal `observation-unknown` until a later observation repairs it. Cancellation persists its intent before asking systemd to stop the service, then preserves an observed systemd success, timeout, or failure result. A `cancelled` result needs matching systemd signal evidence, or a durably recorded successful stop acknowledgement for the observed invocation when systemd has already garbage-collected the transient unit. If a stop times out and the unit later disappears, the job remains nonterminal `outcome-unknown` instead of treating the missing unit's default success fields as an exit result. A later authoritative systemd observation can repair that state. A typed result can prove semantic success after collection only when its content is valid and the capture completion marker proves the producer exited successfully; an empty, partial, malformed, or unmarked result is not completion evidence. A schema-v3 attested-agent record also carries forward its native completion only when systemd still reports an inactive loaded success, its durable lifecycle is `succeeded` with exit status zero, its bounded last-message artifact is valid, and no cancellation intent exists. Existing false terminal success or cancellation records without this evidence are reopened lazily by `get`, `list`, `wait`, or `cancel` and reconciled under the same rules. Systemd remains authoritative for the process, cgroup, timeout, terminal result, cancellation, and journal evidence.

## Completion events, wait-any, and supervision

The capture helper notifies the daemon socket when the captured process exits (both success and failure), so a blocked `job.wait` wakes immediately instead of on its next poll slice. The notification is a best-effort accelerator: systemd observation remains the sole state authority, a missed event is recovered by the fallback observation cadence, and a spurious event costs one bounded extra observation. Server-side waits block on the in-process terminal-event condition (no busy polling), accept up to 3600 seconds, and `job wait <id...> --any` returns the first job of a set to reach a terminal state along with `completed_job_id`. Re-observations that would change nothing but their own timestamp skip the durable record rewrite.

On each first-observed terminal transition the daemon appends one JSON line — `{job_id, kind, project, phase, completed_at, checkout}` — to the event spool (`--event-spool`, default `/realm/state/agentctl/events.jsonl`). The spool is an append-only advisory watch point for supervisors (tail it instead of polling `job status`); it is never state authority, is written at most once per transition per daemon process, and rolls to `events.jsonl.old` past 64 MiB. The gateway watches complete spool records and sends MCP `resources/updated` notifications for `sinnix://gateway/v2/events`, so subscribed coordinator sessions can read the bounded event page without a per-job watcher. A per-job `on_complete` hook is deliberately not implemented: the spool plus push notification and `wait --any` cover supervision without giving jobs ambient exec authority.

`agentctl agent list|status|wait|result` are supervision sugar over the same job routes filtered to `kind=attested-agent`; `agentctl agent launch` is an explicit alias for the bare dispatch form, and `job list --kind` filters any listing by job kind. Agent launches may carry a bounded `--coordinator-label` (also accepted as `--coordinator` or `--campaign-label`); it is recorded in the public job spec and copied to that job's terminal spool events so concurrent campaign monitors can filter their own lanes. Every attested-agent environment carries `BEADS_ACTOR=agent-<job id>` unless the project descriptor declares an explicit value, so task-authority writes from agents never default to the operator's identity. Terminal job records older than the 14-day retention window move to `jobs-archive/` at daemon start; archived records stay loadable by id while listings stop paying for unbounded history.

Project descriptors may declare `[environment.values]` (explicit variable values) and `environment.require` (names that must be present in the resolved job environment). A required variable that is absent at job build time fails the dispatch loudly with the missing names; the silent inherit-filter drop is reserved for variables nothing requires.

## Source-scoped owner adapters

A project descriptor can declare a source-scoped, read-only owner adapter in `[owner_adapters.<name>]`. Each declaration names a non-overlapping canonical namespace, owner identity, protocol versions, canonical source reference, fixed executable, and bounded timeout. AgentCTL sends the request envelope to that exact executable through a transient user service. It does not pass caller-selected argv.

The first reserved contract is `polylogue.archive.status`, owned by `polylogue-archive` and bound to `sinnix://polylogue/archive`. A successful response must use the same request and correlation IDs, retain the declared owner identity, carry exactly one matching source binding, and use a bounded inline or opaque payload. An optional `expected_source_binding` request field is an AgentCTL precondition. When present, the returned generation and root digest must match it exactly. The adapter owns archive semantics and availability errors. AgentCTL owns transport, validation, systemd lifecycle, and result bounds.

## Workspace relationships

Projects may declare a `git-worktree` policy with one absolute workspace root, a default base, an identity check, and checkpoint intent. AgentCTL can create a named linked worktree beneath that exact root or adopt an already registered linked worktree. It stores only the durable relationship: project, stable workspace ID, canonical path, branch, base, creation time, and whether AgentCTL created it. `workspace.list` serves the stored relationship with a bounded filesystem-only state (`available`, `missing`, or `invalid`) and does not revalidate Git identity; `workspace.get` and mutating operations remain authoritative for refs, HEAD, worktree membership, and dirty state.

Create, adopt, checkpoint, restore, and reap require the `agent-control` or `operator` principal. Names are bounded path-safe identifiers, branches pass `git check-ref-format`, bases must resolve to commits, the configured root cannot be adopted, and duplicate names or paths fail closed under a shared mutation lock. A daemon restart reloads the relationship index. List sweeps missing relationships under that lock, preserves them in the response as `missing`, removes eligible records and stack references, and appends one audit note listing the removed IDs and paths. Reap and dispose similarly forget a missing relationship without attempting Git branch deletion. Reap otherwise removes only an AgentCTL-created worktree that is clean, still on its recorded branch, and whose HEAD is contained in the declared base. It retains the branch for explicit review. Adopted, dirty, divergent, and identity-changed worktrees are preserved.

Checkpoint stores separate binary patches for the index and working tree plus a bounded private archive of policy-allowed untracked regular files. Every artifact has a SHA-256 digest and is bound to the workspace, project, branch, and exact source HEAD. Restore requires a clean target at that same HEAD and branch, reruns the descriptor identity check, verifies every artifact digest and archive member, then reconstructs staged, unstaged, and untracked state. It never creates a stash or commit.

A stacked workspace records only its stable parent relationship; Git remains the history authority. Restack requires a clean child, reports overlaps on declared exact-file and generated surfaces before mutation, then rebases the child onto the parent's current branch and aborts a failed Git rebase. A parent cannot be reaped while children still reference it.

Publication requires a successful operation listed by the project as a workspace verifier, bound to the same checkout ID and current exact HEAD. AgentCTL pushes that branch and creates a GitHub review, but stores no PR ledger: review status, mergeability, head identity, and merged state are queried fresh from GitHub. Land rechecks the verification and GitHub head before requesting a squash merge. Finish is the hosted-review path. It requires GitHub to report that exact head merged, deletes the remote branch when present, removes the clean managed worktree and local branch, then removes its relationship and checkpoints. Dispose is the no-PR path for a verification-only managed workspace. It requires a clean, branch-identical workspace with no stacked children, proves its HEAD is contained in the declared base, validates every checkpoint artifact, and refuses any checkpoint with staged, unstaged, or untracked content. It then removes the worktree, local branch, relationship, and empty checkpoints. Reap continues to reclaim a clean base-contained managed worktree while retaining its local branch.

## Adaptive admission and result reuse

Declared operations enter one durable admission record before systemd starts anything. Descriptors may declare `dependencies`, `exclusive_keys`, `estimate_memory_bytes`, and `scratch`. Dependencies are other named operations, exclusive keys are project-defined semantic locks, and scratch is `none`, `tmpfs`, or `nvme`. The daemon validates every name and value while loading the descriptor. It does not derive any of them from an executable name.

A dependency that owns a declared development-service lease is satisfied when its systemd job is active, every leased loopback port is bound, and a `project-command` service has atomically published its job-bound readiness marker. The dependent operation receives exactly those descriptor-named port variables in its private launch environment; the allocated values do not enter the tree-and-environment cache identity. Failed or missing service dependencies still fail closed like ordinary dependencies.

The `interactive`, `normal`, `bulk`, and `agent` pools have separate worker and estimated-memory budgets. Admission also reserves memory for the desktop and blocks non-interactive work under host memory, swap, or I/O pressure. If severe pressure persists, the scheduler cancels the managed non-interactive job with the largest current memory and swap footprint, records the pressure evidence, and reassesses before canceling another. Interactive jobs are never pressure victims. Systemd-oomd is the independent cgroup safety net.

A terminal or pre-cancellation systemd observation records `MemoryPeak` with headroom as the next estimate for that semantic operation. Estimates use a five-run high-water window; a legacy entry without recent samples is replaced by the next observation rather than carried forward. Operators can inspect the durable holder claims, queue order, and blocking arithmetic with `agentctl job admission`, clear one learned estimate with `agentctl job admission-reset <estimate-key>`, or clear all learned estimates with `agentctl job admission-reset --all`. These operations do not alter active jobs or successful-result cache entries. Estimates can rise but never erase a larger declared or learned requirement. Local failures such as OOM kills are terminal; only an ordinary backend exit carrying a recognized provider-capacity response is retryable. Learned estimates, holder claims, and successful-result cache entries are bounded durable state. If that state is malformed or unavailable after restart, it is discarded and durable job records plus systemd remain authoritative.

`tree+environment` caching uses the declared operation, normalized input digest, clean Git tree, and declared environment. A matching running job has one systemd service and one shared durable job ID for all subscribers, so cancellation is shared too. A matching successful record is returned as a reuse. Dirty or unobservable trees do not reuse results. A failed, cancelled, missing, or unobserved result is never cacheable.

Scratch is allocated only under the daemon's owned tmpfs or NVMe roots and is passed through `TMPDIR`. The scheduler removes it after every terminal systemd outcome. Startup repeats cleanup only for already-terminal durable records, so recovery never guesses that a live service has stopped.

Result parsing is pure and bounded. `exit` reads the observed systemd exit result, `json` and `pytest` require a JSON object result artifact, and an attested agent returns its bounded final-message artifact. Systemd still owns the process, cgroup, timeout, cancellation, and journal evidence.

The daemon owns bounded descriptor-declared development-service leases and typed shells only through their stated contracts. It does not own arbitrary shells, product readiness, Git history, hosted review state, or merge state. Beads remains the task-state authority and GitHub remains authoritative for reviews and merges. The gateway’s legacy controllers remain downstream and are unchanged here.

## Generic project plans

`plan.submit` accepts one bounded serializable DAG and materializes every node as an ordinary inspectable `declared-operation` job. Nodes may name different operations, or the plan may name one operation with `plan_node = true` and supply one validated `payload` object per node. Payload validation and fixed argv derivation reuse the operation's descriptor-owned parameter schema. Sinnixd does not interpret the payload or result domain.

The service API is owned by `project-plans`:

```text
plan.submit  {project_id, input_generation, nodes, [node_operation], [workspace_id|checkout_id]}
plan.get     {plan_id}
plan.list    {[project_id]}
plan.wait    {plan_id, [timeout_seconds]}
plan.result  {plan_id, [max_bytes]}
```

The CLI equivalents are `agentctl plan submit`, `get`, `list`, `wait`, and `result`. `plan submit` reads a bounded JSON node file. A node has `node_id` (or `id`), `depends_on` (or `dependencies`), and either `operation` plus `parameters`, or `payload` when `node_operation` is supplied. The graph is checked for duplicate IDs, undeclared dependencies, cycles, node and edge bounds, and descriptor parameter validity before any job is created.

Each plan node stores only its ID, operation, parameter digest, input generation, dependency node IDs, exact registered checkout identity, job ID, and bounded result references. Its durable job carries the plan and node identity and explicit dependency job IDs. Normal-pool admission therefore starts independent ready nodes concurrently and applies descriptor `exclusive_keys`, including project-defined promotion locks, through the existing scheduler. Systemd remains the process, timeout, cancellation, and terminal-result authority.

Repeated plans do not use the ordinary operation cache. A completed node is reusable only when the prior plan's project, exact checkout and HEAD, node operation, parameter digest, node input generation, dependency-node list, and authoritative bounded result evidence all match. Running, failed, cancelled, missing, malformed, or artifact-less jobs are never reused. A plan manifest and node jobs survive daemon restart; recovery finds already-created node jobs by their durable plan and node identity, preserving their logs and results.

For Lynchpin integration, its descriptor must mark the node operation with `plan_node = true`, declare every accepted payload field under `[operations.<node-operation>.parameters]`, and set the operation's `exec`, `pool`, `result`, `cache`, `timeout_seconds`, `exclusive_keys`, `estimate_memory_bytes`, and `scratch` fields as appropriate. Each submission must provide a bounded stable `input_generation` and a node list whose payloads contain no undeclared fields. A node operation should use `result = "json"` or `result = "pytest"` when Lynchpin needs a typed receipt. Lynchpin owns the generation value and convergence semantics; Sinnixd only preserves and compares it.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its pool, timeout, dependencies, result contract, cache policy, exclusivity keys, resource seed, and scratch policy. The daemon supplies admission and lifecycle mechanics. It does not infer semantics from a command basename.

The Polylogue adapter can declare the harvest operation with `result = "json"` and executable `sinnixd-harvest`. `agentctl lane publish <workspace> [--close]` is the publication route: one invocation resolves the workspace, derives the lane job and bead from the job records, mints the review receipt, and authorizes it, reading the PR title/body and close reason from the worktree's `.lane/` artifacts. The publication repo comes from the worktree's `origin` remote. Scanner red flags are computed and recorded on the receipt for audit either way. The two-step route (an unauthorised invocation compiling a `review-required` receipt, then a second `--authorize` invocation naming `receipt_ref`) remains for the reactor's judgment path and for coordinators who want to read the receipt before publishing. `HARVEST_OK`, `REBASE_CONFLICT`, and `GATE_RED` are typed JSON outcomes; unexpected dependency failures remain failed jobs. An affected-verification refusal (`unavailable`) is spooled as a `verification-unavailable` event.
