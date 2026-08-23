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

The service passes a declarative, non-empty `sinnix.services.sinnixd.projectRoots` list as repeated `--project-root` arguments. It defaults to the Sinnix, Polylogue, and Sinex roots. Sinnixd loads only those `.agentctl/project.toml` adapters and does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata.

`job start` accepts a project ID, one declared operation name, an optional workspace binding, and an optional JSON parameters object. It never accepts an arbitrary command. Its optional workspace binding launches in that registered checkout and durably records the checkout ID and exact starting HEAD, so later publication can reject stale verification. Declared operations and internal synthetic foreground commands construct the same durable generic-job spec, record, transient user `.service` launch, log artifact, reconciliation, wait, and cancellation route. The only additional public starts are the constrained typed contracts below.

## Declared-operation parameters and results

Operation parameters are descriptor-owned. The server accepts only parameter names and types declared under that operation, converts them to a fixed argument vector without a shell, and rejects unknown fields, malformed values, missing bounds, and values beyond those bounds. There is no caller-controlled argv, environment, working directory, or timeout on this route.

The initial closed type set is deliberately small:

```toml
[operations.check_default.parameters.full]
type = "bool"
flag = "--full"

[operations.check_default.parameters.package]
type = "string-list"
flag = "--package"
max_items = 16
max_length = 64
```

`bool` emits its declared flag only when true. `string-list` accepts non-empty Cargo-style package names, deduplicates and sorts them, then emits its fixed flag once per value. For the example above, `{"package":["xtask","sinexd","xtask"],"full":true}` becomes `xtask check --full --package sinexd --package xtask` before the declared environment prefix is applied. False booleans and absent parameters do not emit argv entries. The normalized non-default object is encoded as sorted compact JSON and SHA-256 hashed. Each declared job record and `job start`, `job get`, and `job list` response exposes only `parameters.digest`, a lowercase 64-hex digest. Raw parameter values are not persisted. Operations with no `[operations.<name>.parameters]` table remain fixed and reject every non-empty parameters object.

Descriptor `result` is executable contract data. `exit` remains log-only. `json` and `pytest` allocate a bounded result artifact, capture stdout separately from the combined log, and require one UTF-8 JSON object. `agentctl job result` returns that object as typed `value`; malformed, injected trailing output, arrays, and overflowed artifacts are rejected. The record persists `result_kind`, and the result artifact metadata exposes its kind and bound. Polylogue currently declares `verify_affected` and `verify_all` as `pytest`, so their JSON receipts are consumable through this route. Its `verify_quick` still declares `exit`; its descriptor must change to `json` or `pytest` before its receipt is consumable, and this repository does not make that cross-repository declaration change.

## Canonical task authority

Every registered project has one Beads authority at `$SINNIXD_TASK_STATE_ROOT/<project>`, defaulting to `/realm/state/tasks/<project>`. Sinnixd passes the exact `<project>/dolt` database through `bd --db` for every task read, mutation, reconcile, and snapshot. The Git checkout remains the working directory for project environment semantics, but neither its branch nor `.beads/issues.jsonl` participates in authority selection. `task.snapshot` exports records from the canonical database into its response; it does not write the checkout export.

An authority remains unavailable until `<project>/authority.json` attests one completed cutover. The receipt binds the project ID, canonical and source database paths, equal SHA-256 digests of source and destination exports, and equal issue-row counts. The source `.beads/dolt` must then be a symlink to the canonical database. Sinnixd rejects a missing or malformed receipt, unequal verification evidence, a missing canonical database, or a separate source database. This makes interrupted bootstrap and dual live authorities fail closed.

The migration is an operator maintenance action and must run once per project. Stop Sinnixd first, ensure no direct `bd` client can write the project, and confirm the source Dolt server is stopped. The following is the exact Sinnix cutover; substitute the project ID and root for Polylogue and Sinex. It retains the original database as `legacy-dolt-pre-cutover` and does not delete either copy.

```bash
set -euo pipefail
project_id=sinnix
project_root=/realm/project/sinnix
task_state_root=/realm/state/tasks
authority_root="$task_state_root/$project_id"
source_database="$project_root/.beads/dolt"
staging_database="$authority_root/dolt.staging"
canonical_database="$authority_root/dolt"
scratch_dir="$(mktemp -d "/realm/tmp/work/task-cutover.${project_id}.XXXXXX")"

systemctl --user stop sinnixd.service
bd --directory "$project_root" dolt stop
test "$(bd --directory "$project_root" dolt status --json | jq -r .running)" = false
test -d "$source_database"
test ! -e "$authority_root"
install -d -m 0700 "$authority_root"

bd --directory "$project_root" --readonly export >"$scratch_dir/source.jsonl"
source_rows="$(bd --directory "$project_root" --readonly sql 'SELECT COUNT(*) AS row_count FROM issues' --json | jq -er '.[0].row_count')"
bd --directory "$project_root" dolt stop
test "$(bd --directory "$project_root" dolt status --json | jq -r .running)" = false

install -m 0600 "$project_root/.beads/config.yaml" "$authority_root/config.yaml"
install -m 0600 "$project_root/.beads/metadata.json" "$authority_root/metadata.json"
cp -a -- "$source_database" "$staging_database"
diff --recursive --brief --no-dereference "$source_database" "$staging_database"

bd --directory "$project_root" --db "$staging_database" --readonly export >"$scratch_dir/destination.jsonl"
destination_rows="$(bd --directory "$project_root" --db "$staging_database" --readonly sql 'SELECT COUNT(*) AS row_count FROM issues' --json | jq -er '.[0].row_count')"
bd --directory "$project_root" --db "$staging_database" dolt stop
cmp "$scratch_dir/source.jsonl" "$scratch_dir/destination.jsonl"
test "$source_rows" -eq "$destination_rows"
source_digest="sha256:$(sha256sum "$scratch_dir/source.jsonl" | awk '{print $1}')"
destination_digest="sha256:$(sha256sum "$scratch_dir/destination.jsonl" | awk '{print $1}')"
test "$source_digest" = "$destination_digest"

mv "$staging_database" "$canonical_database"
mv "$source_database" "$authority_root/legacy-dolt-pre-cutover"
ln -s "$canonical_database" "$source_database"
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
test "$(readlink -f "$source_database")" = "$canonical_database"
systemctl --user start sinnixd.service
```

If any verification or cutover command fails, leave Sinnixd stopped. Before the two `mv` commands, the source remains authoritative and the incomplete destination has no receipt. After those commands, either finish the symlink and receipt or move `legacy-dolt-pre-cutover` back to `.beads/dolt`; Sinnixd will refuse task operations until one state is unambiguous.

## Typed shell and agent contracts

`agentctl shell` is an explicit operator capability. It accepts an exact argv, a relative working directory inside an explicit registered Git checkout, a timeout, and only the `exit-status` result kind. `agentctl agent` is an explicit `agent-control` capability. It accepts a private prompt file plus a declared backend, model, effort, credential profile, timeout, and only the `last-message` result kind. Observer and local-default principals cannot use either route.

Both routes use the same UUID job ID, transient user service, cancellation, reconciliation, `job get/list/logs/result/wait`, and bounded artifact readers as declared operations. Their durable public record contains the principal, job kind, canonical project and checkout identity, redacted argv digest or prompt digest, and bounded artifact references. It never stores raw shell argv arguments after launch, prompt text, environment values, or credentials.

Typed jobs accept no environment overlay. The daemon creates the `env -i` environment from the declared project environment and fixed `SINNIXD_*` identity fields. Immediately before execution, the contract runner verifies those fields, rechecks the exact registered project, canonical worktree root, common Git directory, porcelain worktree membership, and recorded HEAD. A changed, missing, symlinked, or spoofed identity fails closed. Agent handoff includes `--registered-project`, `--expected-git-common-dir`, and the canonical checkout path; nested scope creation remains disabled, so the native runner provides backend execution and native attestation while the shared transient user service remains the sole process, cgroup, timeout, and cancellation authority. Private launch inputs are mode 0600, removed before shell execution, and removed after agent handoff or every terminal lifecycle outcome, including confirmed launch failure. Native private logs are removed after handoff; only the bounded shared log and result artifacts remain addressable.

Each record is stored under `$XDG_STATE_HOME/sinnixd` and contains safe operation identity, environment key names, and its bounded-read log artifact path. Record replacement fsyncs the containing directory, and newly created state directories are synchronized before they contain durable evidence. The `sinnixd-job-*.service` dynamic runtime surface and its record capture lane are declared with the daemon, rather than with any MCP frontend. Internal foreground argv is launch-only: the durable record has only a SHA-256 digest and constant display metadata, never raw argv or environment values. The systemd-launched capture helper drains output but writes at most 1 MiB per job; it creates its overflow marker with the first discarded byte, so a live log reader can see truncation before the producer exits. It also fsyncs a completion marker only after the captured process exits successfully and all bounded outputs are durable. It does not own a PID, process state, queue, task, workspace, or retry policy. A job ID deterministically derives its unit name. Every `systemd-run` and `systemctl` call has a short finite bound. `job.wait` caps each reconciliation call to its remaining deadline, so a stalled user manager cannot hold a wait or reserved control worker indefinitely. After a daemon restart, `get`, `list`, `wait`, and `cancel` reload the record and reconcile with the user manager. If `systemd-run` loses its reply but `show` finds the transient unit, `job start` returns the reconciled systemd state. If both the launch reply and its first reconciliation are unavailable, `job start` returns a durable nonterminal `launch-unknown` result with the stable job ID and unit. Later `get`, `wait`, and `cancel` use that same identity to reconcile it. A confirmed absent launch becomes terminal `launch-failed`. A confirmed missing unit after launch remains terminal `missing`; an unreachable or timed-out systemd observation is durable nonterminal `observation-unknown` until a later observation repairs it. Cancellation persists its intent before asking systemd to stop the service, then preserves an observed systemd success, timeout, or failure result. A `cancelled` result needs matching systemd signal evidence, or a durably recorded successful stop acknowledgement for the observed invocation when systemd has already garbage-collected the transient unit. If a stop times out and the unit later disappears, the job remains nonterminal `outcome-unknown` instead of treating the missing unit's default success fields as an exit result. A later authoritative systemd observation can repair that state. A typed result can prove semantic success after collection only when its content is valid and the capture completion marker proves the producer exited successfully; an empty, partial, malformed, or unmarked result is not completion evidence. Existing false terminal success or cancellation records without this evidence are reopened lazily by `get`, `list`, `wait`, or `cancel` and reconciled under the same rules. Systemd remains authoritative for the process, cgroup, timeout, terminal result, cancellation, and journal evidence.

## Source-scoped owner adapters

A project descriptor can declare a source-scoped, read-only owner adapter in `[owner_adapters.<name>]`. Each declaration names a non-overlapping canonical namespace, owner identity, protocol versions, canonical source reference, fixed executable, and bounded timeout. AgentCTL sends the request envelope to that exact executable through a transient user service. It does not pass caller-selected argv.

The first reserved contract is `polylogue.archive.status`, owned by `polylogue-archive` and bound to `sinnix://polylogue/archive`. A successful response must use the same request and correlation IDs, retain the declared owner identity, carry exactly one matching source binding, and use a bounded inline or opaque payload. An optional `expected_source_binding` request field is an AgentCTL precondition. When present, the returned generation and root digest must match it exactly. The adapter owns archive semantics and availability errors. AgentCTL owns transport, validation, systemd lifecycle, and result bounds.

## Workspace relationships

Projects may declare a `git-worktree` policy with one absolute workspace root, a default base, an identity check, and checkpoint intent. AgentCTL can create a named linked worktree beneath that exact root or adopt an already registered linked worktree. It stores only the durable relationship: project, stable workspace ID, canonical path, branch, base, creation time, and whether AgentCTL created it. Git remains authoritative for refs, HEAD, worktree membership, and dirty state, which are re-read for every status response.

Create, adopt, checkpoint, restore, and reap require the `agent-control` or `operator` principal. Names are bounded path-safe identifiers, branches pass `git check-ref-format`, bases must resolve to commits, the configured root cannot be adopted, and duplicate names or paths fail closed under a shared mutation lock. A daemon restart reloads the relationship index and derives current state from Git. Reap forgets an already-missing relationship, or removes only an AgentCTL-created worktree that is clean, still on its recorded branch, and whose HEAD is contained in the declared base. It retains the branch for explicit review. Adopted, dirty, divergent, and identity-changed worktrees are preserved.

Checkpoint stores separate binary patches for the index and working tree plus a bounded private archive of policy-allowed untracked regular files. Every artifact has a SHA-256 digest and is bound to the workspace, project, branch, and exact source HEAD. Restore requires a clean target at that same HEAD and branch, reruns the descriptor identity check, verifies every artifact digest and archive member, then reconstructs staged, unstaged, and untracked state. It never creates a stash or commit.

A stacked workspace records only its stable parent relationship; Git remains the history authority. Restack requires a clean child, reports overlaps on declared exact-file and generated surfaces before mutation, then rebases the child onto the parent's current branch and aborts a failed Git rebase. A parent cannot be reaped while children still reference it.

Publication requires a successful operation listed by the project as a workspace verifier, bound to the same checkout ID and current exact HEAD. AgentCTL pushes that branch and creates a GitHub review, but stores no PR ledger: review status, mergeability, head identity, and merged state are queried fresh from GitHub. Land rechecks the verification and GitHub head before requesting a squash merge. Finish is the hosted-review path. It requires GitHub to report that exact head merged, deletes the remote branch when present, removes the clean managed worktree and local branch, then removes its relationship and checkpoints. Dispose is the no-PR path for a verification-only managed workspace. It requires a clean, branch-identical workspace with no stacked children, proves its HEAD is contained in the declared base, validates every checkpoint artifact, and refuses any checkpoint with staged, unstaged, or untracked content. It then removes the worktree, local branch, relationship, and empty checkpoints. Reap continues to reclaim a clean base-contained managed worktree while retaining its local branch.

The daemon still does not own job queues, retries, task mutation, service leases, arbitrary shells beyond the typed operator contract, admission policy, Git history, hosted review state, or merge state. GitHub remains authoritative for reviews and merges; AgentCTL only applies typed transitions after re-reading it. Descriptor pool, cache, and exclusivity metadata remain descriptive until their existing authorities move behind an explicit shared contract. The gateway’s legacy controllers remain downstream and are unchanged here.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its intended pool, result contract, cache policy, and exclusivity keys. The daemon will later supply admission and lifecycle mechanics. It does not infer semantics from a command basename.
