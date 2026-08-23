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
agentctl workspace stack <parent-workspace-id> child-lane --branch feature/child
agentctl workspace restack <child-workspace-id>
agentctl workspace reap <workspace-id>
agentctl job start sinnix lint
agentctl job get <job-id>
agentctl job list
agentctl job wait <job-id>
agentctl job logs <job-id> --max-bytes 64000
agentctl job result <job-id> --max-bytes 64000
agentctl job cancel <job-id>
agentctl shell --project sinnix --checkout default --cwd . -- printf 'harmless command\n'
agentctl agent --project sinnix --checkout default --prompt-file ./prompt.md --backend codex --model gpt-5.6-terra --effort high
```

The service passes a declarative, non-empty `sinnix.services.sinnixd.projectRoots` list as repeated `--project-root` arguments. It defaults to the Sinnix root and `/realm/project/polylogue`. Sinnixd loads only those `.agentctl/project.toml` adapters and does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata.

`job start` accepts a project ID and one declared operation name, never an arbitrary command. Declared operations and internal synthetic foreground commands construct the same durable generic-job spec, record, transient user `.service` launch, log artifact, reconciliation, wait, and cancellation route. The only additional public starts are the constrained typed contracts below.

## Typed shell and agent contracts

`agentctl shell` is an explicit operator capability. It accepts an exact argv, a relative working directory inside an explicit registered Git checkout, a timeout, and only the `exit-status` result kind. `agentctl agent` is an explicit `agent-control` capability. It accepts a private prompt file plus a declared backend, model, effort, credential profile, timeout, and only the `last-message` result kind. Observer and local-default principals cannot use either route.

Both routes use the same UUID job ID, transient user service, cancellation, reconciliation, `job get/list/logs/result/wait`, and bounded artifact readers as declared operations. Their durable public record contains the principal, job kind, canonical project and checkout identity, redacted argv digest or prompt digest, and bounded artifact references. It never stores raw shell argv arguments after launch, prompt text, environment values, or credentials.

Typed jobs accept no environment overlay. The daemon creates the `env -i` environment from the declared project environment and fixed `SINNIXD_*` identity fields. Immediately before execution, the contract runner verifies those fields, rechecks the exact registered project, canonical worktree root, common Git directory, porcelain worktree membership, and recorded HEAD. A changed, missing, symlinked, or spoofed identity fails closed. Agent handoff includes `--registered-project`, `--expected-git-common-dir`, and the canonical checkout path; nested scope creation remains disabled, so the native runner provides backend execution and native attestation while the shared transient user service remains the sole process, cgroup, timeout, and cancellation authority. Private launch inputs are mode 0600, removed before shell execution, and removed after agent handoff or every terminal lifecycle outcome, including confirmed launch failure. Native private logs are removed after handoff; only the bounded shared log and result artifacts remain addressable.

Each record is stored under `$XDG_STATE_HOME/sinnixd` and contains safe operation identity, environment key names, and its bounded-read log artifact path. Record replacement fsyncs the containing directory, and newly created state directories are synchronized before they contain durable evidence. The `sinnixd-job-*.service` dynamic runtime surface and its record capture lane are declared with the daemon, rather than with any MCP frontend. Internal foreground argv is launch-only: the durable record has only a SHA-256 digest and constant display metadata, never raw argv or environment values. The systemd-launched capture helper drains output but writes at most 1 MiB per job; it creates its overflow marker with the first discarded byte, so a live log reader can see truncation before the producer exits. It does not own a PID, process state, queue, task, workspace, or retry policy. A job ID deterministically derives its unit name. Every `systemd-run` and `systemctl` call has a short finite bound. `job.wait` caps each reconciliation call to its remaining deadline, so a stalled user manager cannot hold a wait or reserved control worker indefinitely. After a daemon restart, `get`, `list`, `wait`, and `cancel` reload the record and reconcile with the user manager. If `systemd-run` loses its reply but `show` finds the transient unit, `job start` returns the reconciled systemd state. If both the launch reply and its first reconciliation are unavailable, `job start` returns a durable nonterminal `launch-unknown` result with the stable job ID and unit. Later `get`, `wait`, and `cancel` use that same identity to reconcile it. A successful transient service that systemd has already garbage-collected remains terminal `succeeded`; a confirmed absent launch becomes terminal `launch-failed`. Later missing or unreachable units after a confirmed launch are terminal `missing` or `lost` results. Cancellation persists its intent before asking systemd to stop the service, then preserves an observed systemd success, timeout, or failure result. A `cancelled` result needs matching systemd signal evidence, or a durably recorded successful stop acknowledgement for the observed invocation when systemd has already garbage-collected the transient unit. Systemd remains authoritative for the process, cgroup, timeout, terminal result, cancellation, and journal evidence.

## Source-scoped owner adapters

A project descriptor can declare a source-scoped, read-only owner adapter in `[owner_adapters.<name>]`. Each declaration names a non-overlapping canonical namespace, owner identity, protocol versions, canonical source reference, fixed executable, and bounded timeout. AgentCTL sends the request envelope to that exact executable through a transient user service. It does not pass caller-selected argv.

The first reserved contract is `polylogue.archive.status`, owned by `polylogue-archive` and bound to `sinnix://polylogue/archive`. A successful response must use the same request and correlation IDs, retain the declared owner identity, carry exactly one matching source binding, and use a bounded inline or opaque payload. An optional `expected_source_binding` request field is an AgentCTL precondition. When present, the returned generation and root digest must match it exactly. The adapter owns archive semantics and availability errors. AgentCTL owns transport, validation, systemd lifecycle, and result bounds.

## Workspace relationships

Projects may declare a `git-worktree` policy with one absolute workspace root, a default base, an identity check, and checkpoint intent. AgentCTL can create a named linked worktree beneath that exact root or adopt an already registered linked worktree. It stores only the durable relationship: project, stable workspace ID, canonical path, branch, base, creation time, and whether AgentCTL created it. Git remains authoritative for refs, HEAD, worktree membership, and dirty state, which are re-read for every status response.

Create, adopt, checkpoint, restore, and reap require the `agent-control` or `operator` principal. Names are bounded path-safe identifiers, branches pass `git check-ref-format`, bases must resolve to commits, the configured root cannot be adopted, and duplicate names or paths fail closed under a shared mutation lock. A daemon restart reloads the relationship index and derives current state from Git. Reap forgets an already-missing relationship, or removes only an AgentCTL-created worktree that is clean, still on its recorded branch, and whose HEAD is contained in the declared base. It retains the branch for explicit review. Adopted, dirty, divergent, and identity-changed worktrees are preserved.

Checkpoint stores separate binary patches for the index and working tree plus a bounded private archive of policy-allowed untracked regular files. Every artifact has a SHA-256 digest and is bound to the workspace, project, branch, and exact source HEAD. Restore requires a clean target at that same HEAD and branch, reruns the descriptor identity check, verifies every artifact digest and archive member, then reconstructs staged, unstaged, and untracked state. It never creates a stash or commit.

A stacked workspace records only its stable parent relationship; Git remains the history authority. Restack requires a clean child, reports overlaps on declared exact-file and generated surfaces before mutation, then rebases the child onto the parent's current branch and aborts a failed Git rebase. A parent cannot be reaped while children still reference it. Publication and landing remain outside this slice.

The daemon still does not own job queues, retries, task mutation, service leases, arbitrary shells beyond the typed operator contract, admission policy, Git history, hosted review state, or merge state. Descriptor pool, cache, and exclusivity metadata remain descriptive until their existing authorities move behind an explicit shared contract. The gateway’s legacy controllers remain downstream and are unchanged here.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its intended pool, result contract, cache policy, and exclusivity keys. The daemon will later supply admission and lifecycle mechanics. It does not infer semantics from a command basename.
