# Sinnixd

`sinnixd` is the host-local runtime behind `agentctl` and the future execution-facing Sinnix MCP routes. It uses a mode-0600 Unix socket at `$XDG_RUNTIME_DIR/sinnixd.sock`. MCP remains a stateless policy frontend. pueue, Git, and project adapters remain authoritative for their own state; task state is `bd`'s.

## Current vertical slice

The deployed slice discovers explicit project adapters and can launch only their declared operations:

```text
agentctl status
agentctl project list
agentctl project get sinnix
agentctl project operations sinnix
agentctl workspace list --project sinnix
agentctl workspace create sinnix my-lane --branch feature/my-lane
agentctl workspace get <workspace-id>
agentctl workspace checkpoint <workspace-id>
agentctl workspace restore <workspace-id> <checkpoint-id>
agentctl workspace restore <workspace-id> <checkpoint-id> --recreate
agentctl workspace publish <workspace-id> --job <job-id> --title 'Review title' --body 'Review body'
agentctl workspace review-status <workspace-id>
agentctl workspace land <workspace-id> --job <job-id>
agentctl workspace finish <workspace-id>
agentctl workspace drop <workspace-id>
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
```

The service passes a declarative, non-empty `sinnix.services.sinnixd.projectRoots` list as repeated `--project-root` arguments. It defaults to the registered Sinnix project entries. Sinnixd loads only those `.agentctl/project.toml` adapters and does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata. A descriptor with a `[workspace]` is agent-capable and must declare non-empty shell-free argv lists for both `environment.command` and `environment.preflight`; the latter runs inside the former from the revalidated checkout before any backend starts. `agentctl project get <id>` publishes that capability and both public argv lists.

The environment contract gate evaluates the configured `sinnix.services.sinnixd.projectRoots` and runs `sinnixd-project-environment-check` against the real descriptors. It reports every missing or invalid required declaration and stops before a host configuration is built or activated. The gate runs for `nix run .#switch`, `nix run .#boot`, `nix run .#test-system`, and the devshell `switch`, `boot`, and `test-system` commands. `test-vm` remains separate because it only builds a guest image and does not activate the live host. Roll out descriptor commits before this Sinnix commit. The minimum declaration for every external agent-capable descriptor is `preflight = ["true"]` under `[environment]`; a project may use a stronger cheap project-native readiness argv instead. The current external prerequisites are Polylogue, Sinex, and Lynchpin, and all three descriptors must satisfy this contract before any gated command is run.

The optional `sinnixd-reactor` user service is the model-free owner of campaign mechanics. Each tick it reads every managed workspace of its refill projects into facts (worktree head, pushed head, holder, newest receipt, the PR the last publication sweep saw) and dispatches the one action `lane_facts.advance` names: verify, harvest, publish, integrate, rebase, review-fix, retry, or park. It parks the bead of a lane that had nothing to publish, refills the wave from the ready frontier under a backoff, and reconciles campaign claims whose lane died. `campaign-board.json` holds only its dispatch markers and a rotating error log. It does not review or select work; those remain fresh-context harvester and strategist responsibilities.

`job start` accepts a project ID, one declared operation name, an optional workspace binding, and an optional JSON parameters object. It never accepts an arbitrary command. Its optional workspace binding launches in that registered checkout and durably records the checkout ID and exact starting HEAD, so later publication can reject stale verification. Declared operations and internal synthetic foreground commands construct the same durable generic-job spec, record, transient user `.service` launch, log artifact, reconciliation, wait, and cancellation route. A descriptor may set a bounded `timeout_seconds`; that becomes the transient service limit, rather than a caller-controlled duration. The typed attested-agent contract also accepts an optional validated Beads binding from the gateway. It is public durable provenance, not prompt material: canonical bead/project/checkout refs, launch task revision and etag, optional claim receipt, request ID, and display-only work item. The only additional public starts are the constrained typed contracts below.

An operation may also declare `schedule = "OnCalendar expression"`. Sinnixd registers each such operation as a persistent transient user-manager timer and reconciles the timer set from a durable schedule map at daemon startup, so a daemon restart does not lose a calendar firing. The timer only invokes the daemon's schedule-fire route; Sinnixd validates the declared schedule and submits an ordinary declared-operation job. Its durable dimensions record the schedule ID, expression, timer unit, and `systemd-timer` trigger, so scheduled work has the same records and events as an explicit start. Scheduled operations cannot require parameters.

## Declared-operation timeout contract

An operation may declare `timeout_seconds` as a positive integer. Omission keeps the 3,600-second default. Declared operations may use at most 28,800 seconds (eight hours), which accommodates finite full suites and long-running source or automaton batches while still providing a fixed systemd deadline. Descriptor parsing rejects booleans, non-integers, zero, negative values, and values above that maximum. The catalog, job response, durable job spec, recovery path, and `RuntimeMaxSec` all carry this one descriptor-owned value. Gateway and MCP clients receive the same catalog and job metadata; they do not accept a second timeout override.

The longer maximum applies only to `declared-operation` jobs. `agentctl shell`, `agentctl agent`, and internal foreground commands retain their existing bounds. In particular, shell and attested-agent jobs remain capped at 3,600 seconds, and the contract runner validates that identity before execution. Declared operations execute through `sinnixd-queue-run` directly rather than that typed-job runner, so extending a suite cannot widen arbitrary command authority.

## Declared-operation parameters and results

Operation parameters are descriptor-owned. The server accepts only parameter names and types declared under that operation, converts them to a fixed argument vector without a shell, and rejects unknown fields, malformed values, missing bounds, and values beyond those bounds. There is no caller-controlled argv, environment, working directory, or timeout on this route.

Each parameter declares exactly one mapping: a long `flag`, or a required `position`. Positional parameters are scalar `string`, `enum`, or `integer` values. They must set `required = true`; optional, list, and boolean positional declarations are invalid. Positions are positive, unique, and contiguous from `1`, so descriptor table order can never choose a positional argv order. Flag parameters retain the existing optional behavior and their descriptor-table order controls only their flag order, regardless of JSON object ordering. The server never invokes a shell.

```toml
[operations.sinex_all_sources]
description = "Run Sinex's all-sources foreground operation"
exec = ["xtask", "run", "all-sources"]
pool = "normal"
result = "exit"

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

`bool` emits its flag only when true. Flag-mapped `string`, `enum`, and `integer` values emit one flag-value pair. `string-list` and `enum-list` require non-empty arrays, deduplicate and sort their values, then repeat the fixed flag once per canonical value. False booleans and absent flag parameters emit nothing. A required positional scalar emits exactly one argv item. Derived argv is always `exec`, then positional values in ascending `position`, then present flags in descriptor-table order. Scalar strings require `max_length`; the optional `grammar` selects one safe grammar, with `safe-token` as the default. The supported grammars are `safe-token` (`[A-Za-z0-9][A-Za-z0-9._:+@=-]*`), `identifier` (`[A-Za-z_][A-Za-z0-9_]*`), `package-name` (`[A-Za-z0-9][A-Za-z0-9_-]*`), and `duration` (`[1-9][0-9]{0,8}(ms|s|m|h)`). Arbitrary descriptor regexes are not accepted. Enum values must be a non-empty, unique safe-token set. Integers require inclusive `min` and `max` within signed 32-bit range. Lists require `max_items` from 1 through 32; strings and enum values are limited to 128 characters, and declared `max_length` must be from 1 through 128. An operation has at most 16 parameters and an enum has at most 64 values. Unknown descriptor fields, malformed definitions, duplicate flags or positional positions, gapped positions, booleans supplied as integers, unsafe strings, empty lists, and out-of-range values are rejected before launch.

For the all-sources example, `{"instance_id":"operator-source-driver-browser.history-3","reconcile":true,"service_name":"source-driver-browser.history-3","include_default_excluded":true}` produces `xtask run all-sources --instance-id operator-source-driver-browser.history-3 --reconcile --service-name source-driver-browser.history-3 --include-default-excluded` before the declared environment prefix. These names match Sinex's source-binding identities, whose defaults are `source-driver-<source_id>-<instance_idx>`. If a project declares the shown closure operation, `{"bead_id":"sinex-a1b2","json":true,"dry_run":true}` produces `xtask verify closure sinex-a1b2 --json --dry-run`; the current Sinex descriptor does not publish that operation. The normalized non-default object, including required positional values, is encoded as sorted compact JSON and SHA-256 hashed. Each declared job record and `job start`, `job get`, and `job list` response exposes only `parameters.digest`, a lowercase 64-hex digest. Raw parameter values are absent from public durable job metadata. The private launch intent may temporarily retain the derived argv and environment while a job needs recovery. Operations with no `[operations.<name>.parameters]` table remain fixed and reject every non-empty parameters object.

Descriptor `result` is executable contract data. `exit` remains log-only. `json` and `pytest` allocate a bounded result artifact, capture stdout separately from the combined log, and require one UTF-8 JSON object. `agentctl job result` returns that object as typed `value`; malformed, injected trailing output, arrays, and overflowed artifacts are rejected. The record persists `result_kind`, and the result artifact metadata exposes its kind and bound. Polylogue currently declares `verify_affected` and `verify_all` as `pytest`, so their JSON receipts are consumable through this route. Its `verify_quick` still declares `exit`; its descriptor must change to `json` or `pytest` before its receipt is consumable, and this repository does not make that cross-repository declaration change.

## Task authority

Task state is `bd`'s alone. The daemon holds no task write path; it sets
`BEADS_ACTOR=agent-<job id>` in every attested-agent environment so an agent's
own writes are not attributed to the operator.

Delivery is a precondition of `workspace.publish` and `workspace.land`, not a caller-fed completion route. Ordinary delivery reads the exact-head declared verification job through `job.result`. Packet delivery additionally names the Beads-bound attested-agent job with `--packet-job`. The declared verification job receives the same immutable Beads identity and write-scope binding at dispatch; each job record independently freezes its checkout head, and the contract runner seals the worker's structured report to the Git head observed when the runner exits. Delivery requires the bindings to match, the later semantic verifier to succeed at that same final head, snapshots the packet's initial-to-final Git range, and checks the complete current base-to-head publication diff against the Beads-owned scope. It rejects dirty, divergent, stale, or out-of-scope publication work and repeats the complete precondition after push and after review inspection. The worker report can only tighten acceptance through bounded anti-vacuity, unresolved-work, delegation-visibility, exact deletion evidence, and evidence-only fields. Git owns paths, commits, and heads; the project verifier owns semantic success; GitHub branch protection owns required review state.

Typed jobs accept no environment overlay. The daemon creates the `env -i` environment from the declared project environment and fixed `SINNIXD_*` identity fields. Immediately before execution, the contract runner verifies those fields, rechecks the exact registered project, canonical worktree root, common Git directory, porcelain worktree membership, and recorded HEAD. A changed, missing, symlinked, or spoofed identity fails closed. Every attested agent runs its mandatory environment `preflight` from the revalidated checkout, then invokes the native backend through the same descriptor-owned `environment.command`. A missing, failed, unavailable, or 30-second `agent-preflight-timeout` preflight terminates the typed job before backend implementation starts and retains an actionable runner error in the bounded log. Attested-agent private inputs use schema v2; v1 records fail closed as stale contract input and must be relaunched. `sinnixd-queue-run` — the command every pueue task runs — is the sole process, timeout, and cancellation authority; it revalidates the bound checkout at its own exec boundary, closing the check-to-exec interval instead of trusting the checkout binding captured when the record was created. Private launch inputs are mode 0600, removed before shell execution, and removed after handoff or every terminal lifecycle outcome, including confirmed launch failure. Native private logs are removed after handoff; only the bounded shared log and result artifacts remain addressable.

Each record is stored under `$XDG_STATE_HOME/sinnixd` and contains safe operation identity, environment key names, and its bounded-read log artifact path. Record replacement fsyncs the containing directory, and newly created state directories are synchronized before they contain durable evidence. Internal foreground argv is launch-only: the durable record has only a SHA-256 digest and constant display metadata, never raw argv or environment values. `sinnixd-queue-run` drains the queued process's output into the bounded shared log, enforces the declared timeout, and writes the typed result artifact when the operation declares one; it owns no PID, process state, queue, workspace, or retry policy beyond the one task pueue gave it. A job's durable identity is a UUID minted by sinnixd; the pueue label `<project_id>:<operation>:<job_id>` and an internal task-id handle carry that identity into pueue, resolved by scanning pueue's tasks by label when the handle is absent or forgotten. Every `pueue` call has a short finite bound. After a daemon restart, `get`, `list`, `wait`, and `cancel` reload the record and reconcile against pueue's own task state, which is the sole state authority. If `pueue add` fails outright, `job start` returns a durable nonterminal `launch-unknown` result; later `get`, `wait`, and `cancel` use the same job ID to retry the observation. A task pueue no longer recognizes (forgotten across a pueue restart, or genuinely never queued) is terminal `missing`; an unreachable pueue observation is durable nonterminal `observation-unknown` until a later observation repairs it. Cancellation persists its intent, then kills pueue's task; a job that never reached pueue (still blocked on dependencies) needs no kill and becomes terminal `cancelled` immediately. A typed result can prove semantic success only when its content is valid; pueue's own `Done`/`Success` result is the completion evidence, so no separate completion marker is needed. Systemd's only remaining role is the calendar-timer wake-up described below; pueue owns the process, timeout, terminal result, and cancellation for every job.

Terminal records also carry the versioned `state.telemetry` machine-run projection. It contains only safe command shape, start and finish timestamps, duration, and explicit backend usage. Project verifiers retain ownership of semantic receipts; Sinnixd does not create a second verification-history store or spool.

## Completion events and supervision

Server-side waits poll pueue's task state on a bounded cadence and block on the in-process terminal-event condition between polls (no busy waiting), accepting up to 3600 seconds. Re-observations that would change nothing but their own timestamp skip the durable record rewrite.

On each first-observed terminal transition the daemon appends one JSON line — `{job_id, kind, project, phase, completed_at, checkout}` — to the event spool (`--event-spool`, default `/realm/state/agentctl/events.jsonl`). The spool is an append-only advisory watch point for supervisors (tail it instead of polling `job get`); it is never state authority, is written at most once per transition per daemon process, and rolls to `events.jsonl.old` past 64 MiB. The gateway watches complete spool records and sends MCP `resources/updated` notifications for `sinnix://gateway/v2/events`, so subscribed coordinator sessions can read the bounded event page without a per-job watcher. A per-job `on_complete` hook is deliberately not implemented: the spool plus push notification cover supervision without giving jobs ambient exec authority.

`agentctl agent launch` is an explicit alias for the bare dispatch form; supervise agent jobs through the `job` verbs with `job list --kind attested-agent`. Agent launches may carry a bounded `--coordinator-label` (also accepted as `--coordinator` or `--campaign-label`); it is recorded in the public job spec and copied to that job's terminal spool events so concurrent campaign monitors can filter their own lanes. Every attested-agent environment carries `BEADS_ACTOR=agent-<job id>` unless the project descriptor declares an explicit value, so task-authority writes from agents never default to the operator's identity. A job record and its artifacts live exactly as long as the thing they served: the workspace that owned the checkout is dropped or finished, the plan that owns the node is gone, or the next terminal run of the same operation on the same checkout supersedes the record. Nothing is deleted on a clock.

Project descriptors may declare `[environment.values]` (explicit variable values) and `environment.require` (names that must be present in the resolved job environment). A required variable that is absent at job build time fails the dispatch loudly with the missing names; the silent inherit-filter drop is reserved for variables nothing requires.

## Workspace relationships

Projects may declare a `git-worktree` policy with one absolute workspace root, a default base, an identity check, and checkpoint intent. `workspace create` runs `wt switch --create <branch> --no-cd -y --format json` in the project's primary checkout with `worktree-path` pinned to the declared root, so the placement is the descriptor's rather than the invoking user's worktrunk config. worktrunk owns creation, the project's own `.config/wt.toml` hooks own provisioning, and `wt remove --reap --foreground` owns removal; a `[workspace.provision]` declaration is parsed but no longer executed by sinnixd. AgentCTL stores only the durable relationship: project, stable workspace ID, canonical path, branch, base, and creation time. `workspace.list` serves the stored relationship with a bounded filesystem-only state (`available`, `missing`, or `invalid`) and does not revalidate Git identity; `workspace.get` and mutating operations remain authoritative for refs, HEAD, worktree membership, and dirty state.

Create, checkpoint, restore, and drop require the `agent-control` or `operator` principal. Names are bounded path-safe identifiers, branches pass `git check-ref-format`, bases must resolve to commits, the configured root cannot be used, and a name or branch that is already registered fails closed under a shared mutation lock without adopting or replacing the registered workspace. A daemon restart reloads the relationship index. List sweeps missing relationships under that lock, preserves them in the response as `missing`, removes eligible records, and appends one audit note listing the removed IDs and paths. Drop forgets a missing relationship without attempting Git branch deletion.

Checkpoint stores separate binary patches for the index and working tree plus a bounded private archive of policy-allowed untracked regular files. Every artifact has a SHA-256 digest and is bound to the workspace, project, branch, and exact source HEAD. Restore requires a clean target at that same HEAD and branch, reruns the descriptor identity check, verifies every artifact digest and archive member, then reconstructs staged, unstaged, and untracked state. It never creates a stash or commit.

Publication requires a successful operation listed by the project as a workspace verifier, bound to the same checkout ID and current exact HEAD. AgentCTL pushes that branch and creates a GitHub review, but stores no PR ledger: review status, mergeability, head identity, and merged state are queried fresh from GitHub. Land rechecks the verification and GitHub head before requesting a squash merge. Finish is the hosted-review path. It requires GitHub to report that exact head merged, deletes the remote branch when present, removes the clean managed worktree and local branch, then removes its relationship and checkpoints.

Drop is the general deletion path. Without `force` the workspace must be clean, hold its declared branch identity, and prove its content is published: contained in the declared base, or carrying worktrunk's `integrated` verdict, which runs six checks including squash patch-id equality. `force` is the operator's acknowledgement that the content is expendable. Drop and finish both delete every job record and artifact bound to that checkout.

## Result parsing

A declared operation's `pool` names its pueue group; pueue owns queueing and per-group parallelism. A job with unmet `dependency_job_ids` (set by a caller, not a descriptor field) holds `waiting-dependencies` until every dependency succeeds, then launches; a failed dependency terminalizes it as `dependency-failed`. Local failures such as OOM kills are terminal; only an ordinary backend exit carrying a recognized provider-capacity response is retryable, with a bounded retry delay.

Result parsing is pure and bounded. `exit` reads the observed pueue exit result, `json` and `pytest` require a JSON object result artifact, and an attested agent returns its bounded final-message artifact. pueue still owns the process, timeout, cancellation, and terminal-result evidence.

The daemon owns typed shells only through their stated contracts. It does not own arbitrary shells, product readiness, Git history, hosted review state, or merge state. `bd` remains the task-state authority and GitHub remains authoritative for reviews and merges. The gateway’s legacy controllers remain downstream and are unchanged here.

## Generic project plans

`plan.submit` accepts one bounded serializable DAG and materializes every node as an ordinary inspectable `declared-operation` job. Nodes may name different operations, or the plan may name one operation with `plan_node = true` and supply one validated `payload` object per node. Payload validation and fixed argv derivation reuse the operation's descriptor-owned parameter schema. Sinnixd does not interpret the payload or result domain.

The service API is owned by `project-plans`:

```text
plan.submit  {project_id, nodes, [node_operation], [workspace_id|checkout_id]}
plan.get     {plan_id}
plan.wait    {plan_id, [timeout_seconds]}
```

The CLI equivalents are `agentctl plan submit`, `get`, and `wait`. `plan submit` reads a bounded JSON node file. A node has `node_id` (or `id`), `depends_on` (or `dependencies`), and either `operation` plus `parameters`, or `payload` when `node_operation` is supplied. The graph is checked for duplicate IDs, undeclared dependencies, cycles, node and edge bounds, and descriptor parameter validity before any job is created.

Each plan node stores only its ID, operation, parameter digest, dependency node IDs, exact registered checkout identity, job ID, and bounded result references. Its durable job carries the plan and node identity and explicit dependency job IDs: a node with unmet dependencies holds `waiting-dependencies` until they succeed, then launches; independent ready nodes launch concurrently, bounded by pueue's per-group parallelism. pueue remains the process, timeout, cancellation, and terminal-result authority.

A resubmitted plan runs its nodes again; nothing is reused from a prior plan. A plan manifest and node jobs survive daemon restart; recovery finds already-created node jobs by their durable plan and node identity, preserving their logs and results.

For Lynchpin integration, its descriptor must mark the node operation with `plan_node = true`, declare every accepted payload field under `[operations.<node-operation>.parameters]`, and set the operation's `exec`, `pool`, `result`, and `timeout_seconds` fields as appropriate. Each submission must provide a node list whose payloads contain no undeclared fields. A node operation should use `result = "json"` or `result = "pytest"` when Lynchpin needs a typed receipt.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means: its pool, timeout, and result contract. The daemon supplies launch and lifecycle mechanics. It does not infer semantics from a command basename.

The Polylogue adapter can declare the harvest operation with `result = "json"` and executable `sinnixd-harvest`. `agentctl lane publish <workspace> [--close]` is the publication route: one invocation resolves the workspace, derives the lane job and bead from the job records, mints the review receipt, and authorizes it, reading the PR title/body and close reason from the worktree's `.lane/` artifacts. The publication repo comes from the worktree's `origin` remote. Scanner red flags are computed and recorded on the receipt for audit either way. The two-step route (an unauthorised invocation compiling a `review-required` receipt, then a second `--authorize` invocation naming `receipt_ref`) remains for the reactor's judgment path and for coordinators who want to read the receipt before publishing. `HARVEST_OK`, `REBASE_CONFLICT`, and `GATE_RED` are typed JSON outcomes; unexpected dependency failures remain failed jobs. An affected-verification refusal (`unavailable`) is spooled as a `verification-unavailable` event.
