# Sinity Environment Contract

Cross-project rules. Repository semantics live in its `CLAUDE.md`;
`AGENTS.md` is an alias. Query runtime and task state from their owners.

## Work and authority

- Carry authorized work to a verified result. Compaction is a continuation,
  not a deadline or a reason to defer substantial work.
- Preserve the requested outcome. State scope and exclusions for multi-step
  work; investigate discoveries that affect it, and record unrelated work
  without silently expanding the task.
- Check the evidence that decides the question. Separate observed facts,
  inferences, and unverified claims. Name the missing evidence when blocked.
- A request to inspect, diagnose, or advise authorizes relevant read-only
  checks. A request to improve or implement authorizes scoped changes and
  normal verification. Ask when authority, irreversible consequences, or the
  intended outcome is genuinely ambiguous.
- Unfinished code is not obsolete. Establish a shipped replacement, recorded
  retirement, or explicit authorization before deleting it. When replacing a
  route, account for its callers, commands, docs, and tests.
- Preserve unrelated edits. Before destructive recovery, resolve exact
  targets, preserve recoverable evidence, and state the intended action.

## Communication and durable text

Load `writing-style` for human-facing prose and `writing-for-agents` when
editing instructions or memory.

- Report the outcome, changed files, exact verification, and residual risk.
  Keep progress updates short and decision-relevant.
- Write each fact once. Comments explain constraints; docs describe current
  behavior; Beads carry problems, evidence, decisions, and wanted outcomes.
  Put incident history in its task, not in always-loaded instructions.
- Use ordinary language. Introduce a new term only when it removes genuine
  ambiguity, and define it where used.
- Keep always-loaded instructions small. Put procedures in skills and facts
  discoverable from commands in their owning tools. Remove superseded advice
  when adding its replacement.
- Read command exit status directly. For large output, capture it and inspect
  deliberately; a pipeline's final status does not prove an earlier check
  passed. Do not pipe verification through `tail` or a summary filter.

## Filesystem and private data

Host: `sinnix-prime`. Root storage is wear-limited; use `/realm` for heavy work.

- `/realm/project/`: active repositories.
- `/realm/`: subject folders and service storage. Read `/realm/INVENTORY.md`;
  mutations go through its owning tools.
- `/realm/state/`: live service state and external Beads databases.
- `/realm/tmp/work/`: private scratch output, aged after 30 days.
  `/realm/worktrees/`: isolated checkouts and compile-heavy work.
- `/tmp` is small tmpfs. `TMPDIR` is managed; do not invent heavy work roots
  there. Home is rebuilt by Home Manager; edit the declared source of managed
  files. Query `xdg-user-dir` for user-facing download/document locations.

Treat tracked files, commits, task exports, CI logs, and publication text as
public. Never put secrets, captures, transcripts, personal databases, or
generated private analyses in them. Synthetic fixtures stay neutral.

## Runtime ownership

Load `agent-runtime` before nontrivial job/worktree recovery and `orchestrate`
before parallel agent work. Consult `agentctl --help` for current verbs.

- Short foreground checks run directly. Detached, queued, resource-heavy,
  and shared work runs through declared project operations:
  `agentctl job start <project> <operation> [--workspace <path>] [--wait]`.
- `agentctl` is an in-process CLI. pueue owns queued jobs and terminal results;
  Git/worktrunk own commits/worktrees; GitHub owns hosted publication; Beads
  owns task state. Systemd owns fixed services and timer wake-ups. Reconcile
  these sources instead of maintaining another ledger.
- Check `agentctl job list --active` before heavy work. Do not duplicate jobs
  or construct background reapers, `systemd-run`, or resource envelopes by hand.
- Act on recorded task IDs and worktree paths, not inferred process names.
  For standalone process searches, bracket a character in `pgrep -f` patterns
  so the search cannot match its own shell command.
- Every dispatch names backend, model, and effort explicitly. Model allocation
  and recovery decisions follow `orchestrate`; a strong coordinator may
  delegate bounded architecture as well as implementation.
- One accountable supervisor owns each concern. Automate evidence collection;
  delegate routine supervision; retain explicit decisions for retries,
  conflicting evidence, acceptance, and destructive actions. Do not repeat a
  delegated inspection without a concrete reason to doubt or extend it.
- Use one event watch per campaign concern, with a named owner. On takeover,
  inventory existing watches before adding one; stop owned watches whose
  purpose has ended. Use completion events, not polling loops.
- Give long work an evidence-based duration expectation. At roughly twice it,
  inspect progress and decide to repair, cancel, or extend with a reason.

## Batches and publication

`agentctl view <project>` and `agentctl batch status <run>` provide current
state. The coordinator contract at
`/realm/project/sinnix/dots/_ai/skills/orchestrate/references/coordinator-contract.md`
owns takeover, dispatch, recovery, and landing procedures.

- A batch has isolated workers on one base and one integrated candidate.
  Start coherent, non-overlapping work; its queued landing task owns
  integration, verification, review, and publication.
- Read the repository rules and memory index before dispatch. Task readiness
  includes its dependencies, remaining design decisions, and required live
  authority. A ready queue entry alone does not establish executability.
- Use `bd` from the owning repository, with an explicit actor. Task state is
  external to feature branches. Read/write tasks through `task-backend`;
  mature their specification through `bead-authoring`.
- Checkpoint before risky integration or recovery. Stage explicit paths and
  inspect the complete staged diff. Never bypass hooks or branch protections.
- Publish through `agentctl batch land <run>` under the repository's declared
  publication policy; load `review-land`. A published partial result does not
  close unmet acceptance criteria.
- Run the corpus once at the deliberate batch/master boundary, not per worker.
  Selected tests, static gates, review, and a full corpus are different evidence.
- Tests exercise behavior, invariants, and reproduced failures. Do not enforce
  natural-language wording or preserve obsolete refactoring details as tests.
- Fix inherited failures forward. Do not turn a transient regression into a
  new permanent serialization gate. Report exactly what was verified and what
  landed without test evidence.

## Desktop and host changes

The operator's Chrome is shared. Agent work uses
`sinnix-chrome-control agent-window`; requests about the operator's tabs use
those existing pages without unrelated navigation or closure. Load
`desktop-control-plane` for browser, Kitty, Hyprland, and screenshot recipes.
`sinnix-observe` provides live host evidence.

Sinnix activation changes the live machine. State affected services/files and
use only its devshell wrappers: `switch`, `boot`, or `test-vm`
(`nix develop --command switch` from `/realm/project/sinnix`). Verify the
activated revision and direct live effect. Source edits alone are not proof
that an installed skill, executable, or service changed.

## History and memory

- Session history: Polylogue; `claude-sessions` reads raw JSONL when needed.
- Cross-source history: Lynchpin. Host evidence: runtime inventory,
  `sinnix-observe`, `/realm/activity/`, and `/realm/machine/`.
- Operator stream: `/realm/journal/raw-log.md`.
- Project memory: `~/.claude/projects/<p>/memory/MEMORY.md`, a short index of
  stable facts and pointers. Verify recalled mechanisms against current code.
  Archive superseded memories with their useful evidence preserved.
- Current work, decisions, and task-shaped lessons belong in Beads; jobs and
  receipts stay with the runtime. Memory points to those owners instead of
  duplicating changing campaign state. Never copy private memory into public
  instructions without reviewing and sanitizing it.
- On recovery, preserve volatile evidence first, then inspect live state,
  Git checkpoints, tasks/history, and backups. Verify recovered content before
  deleting a source. Load `investigate` for ambiguous recovery.
