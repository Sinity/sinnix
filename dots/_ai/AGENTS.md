# Operator environment

Rules for every agent on this machine, in every repository. A repository's
`AGENTS.md` owns its own semantics. Runtime and task state live with the owners
named below, not in instructions.

## Work

- Carry authorized work to a verified result. Compaction continues the work; it
  is not a deadline or a reason to defer.
- A request to inspect, diagnose, or advise authorizes read-only checks. A
  request to improve or implement authorizes scoped changes and their normal
  verification. Ask only when authority, an irreversible consequence, or the
  intended outcome is genuinely ambiguous.
- Keep the requested outcome. For multi-step work, state scope and exclusions;
  follow discoveries that affect the outcome and record the rest instead of
  silently widening the task.
- Decide from the evidence that settles the question. Keep observations,
  inferences, and unverified claims apart. When blocked, name the missing
  evidence.
- Write code in coherent batches. Read the requirements and the call paths,
  write the whole connected change (callers, tests, docs, generated files),
  then verify once. A test run after every small edit spends the speed an agent
  has; run a quick probe only to settle a concrete uncertainty.
- When a replacement ships, remove its predecessor together with its callers,
  commands, docs, and tests. Do not keep a compatibility path beside it.
  Unfinished code is not obsolete: deleting it needs a shipped replacement, a
  recorded retirement, or explicit authorization.
- Preserve unrelated edits. Before destructive recovery, resolve the exact
  targets, preserve recoverable evidence, and state the intended action.

## Reporting and durable text

Load `writing-style` for prose people read and `writing-for-agents` for
instructions, skills, and memory.

- Report the outcome, changed files, exact verification, and residual risk.
  Keep progress updates short and decision-relevant.
- Write each fact once, where it is owned: comments hold constraints, docs hold
  current behavior, Beads hold problems, decisions, and evidence. Incident
  history belongs in its task, never in always-loaded instructions.
- Use ordinary language. Coin a term only when it removes real ambiguity, and
  define it at first use.
- Read exit statuses directly. Capture large output and inspect it on purpose;
  a pipeline's final status says nothing about earlier stages, so never pipe
  verification through `tail` or a summarizing filter.
- Before compaction or stopping mid-work, leave a handoff: active job IDs and
  worktrees, Bead IDs and claims, exact Git state, changed files, verification
  already run, and the single next action. On re-entry, verify those records
  instead of trusting a summary.

## Filesystem and private data

Host `sinnix-prime`. Root storage is wear-limited; heavy work belongs on
`/realm`.

- `/realm/project/`: active repositories. `/realm/worktrees/`: isolated
  checkouts and compile-heavy work.
- `/realm/`: subject folders and service storage; read `/realm/INVENTORY.md`
  and mutate through the owning tools. `/realm/state/`: live service state and
  the external Beads databases.
- `/realm/tmp/work/` is the managed `$TMPDIR`. Put scratch in a per-task
  subdirectory and remove it when done; retained results go to their owning
  store. `/tmp` is a small tmpfs.
- Home Manager rebuilds `$HOME`; edit the declared source of a managed file.
  `xdg-user-dir` gives user-facing download and document locations.

Tracked files, commits, task exports, CI logs, and PR text are public. Keep
secrets, captures, transcripts, personal databases, and private analyses out of
them; test fixtures stay synthetic and neutral.

## Runtime

Load `agent-runtime` before AgentCTL job or batch work and `orchestrate` before
running agents in parallel.

- Each kind of state has one owner: pueue for queued jobs and their results,
  Git and worktrunk for commits and worktrees, GitHub for hosted publication,
  Beads for tasks, systemd for fixed services and timers. `agentctl` is a CLI
  over them; reconcile these sources rather than keeping another ledger.
- Short foreground checks run directly. Queued, heavy, detached, or shared work
  runs as a declared operation:
  `agentctl job start <project> <operation> [options] [-- <declared args>]`.
  Take syntax from `agentctl <verb> --help` and
  `/realm/project/sinnix/docs/agentctl.md`. On an error, read the message and
  those sources; never guess syntax or repeat a mutation whose result is
  unclear.
- Act on recorded job IDs, task IDs, and worktree paths, not inferred process
  names. In `pgrep -f` patterns, bracket one character so the search cannot
  match itself.
- One accountable owner per concern, with one event watch; wait on completion
  events rather than polling. Give long work an evidence-based duration and, at
  about twice that, inspect it and decide to repair, cancel, or extend.

## Delivery

- Read the target checkout's `AGENTS.md` before dispatching or editing. Project
  memory supplies decisions that code and Beads cannot; it never overrides
  them.
- Use `bd` from the owning repository with an explicit `--actor`; load `beads`
  to read, change, or write tasks.
- Run focused checks for the contract you changed. Affected or full suites need
  an explicit operator request. Tests exercise behavior, invariants, and
  reproduced failures, never prose wording or refactoring detail. Fix inherited
  failures forward, and report exactly what ran.
- Stage explicit paths and review the complete staged diff. Never bypass hooks
  or branch protection.
- Where a forge runs a hosted reviewer on PRs, that review is the independent
  review; add a reviewer agent only for a named risk it cannot cover. A PR
  merges when its required statuses pass, the hosted review has completed on
  the exact head, and every review thread is answered with a fix commit or a
  concrete refutation and then resolved. Where the forge enforces these
  (required statuses, conversation resolution), merge with
  `gh pr merge --auto --squash --match-head-commit <sha>` and let it gate.
  Findings that arrive after a merge become a follow-up commit or Bead.
- A partial delivery leaves its unmet acceptance criteria open.

## Desktop and host changes

- The operator's Chrome is shared. Check `sinnix-chrome-control status`, and
  retry and inspect `list-tabs` before concluding it is unavailable. Agent work
  uses its own agent window or background tab by page ID; the operator's tabs
  are touched only when a request is about them. Load `desktop-control-plane`
  for browser, Kitty, Hyprland, and screenshot work. `sinnix-observe` gives live
  host evidence.
- Sinnix activation changes the live machine. Use only the devshell wrappers
  (`nix develop --command switch|boot|test-vm` from a Sinnix checkout), state
  the affected services and files, then verify the activated revision and the
  direct live effect. An edited source proves nothing about what is installed.

## History and memory

- Session history: Polylogue, or `claude-sessions` for raw Claude transcripts.
  Cross-source history: Lynchpin. Host evidence: the runtime inventory,
  `sinnix-observe`, `/realm/activity/`, `/realm/machine/`. Operator stream:
  `/realm/journal/raw-log.md`.
- Project memory (`~/.claude/projects/<project>/memory/MEMORY.md`) is a short
  index of stable facts and pointers. Verify recalled mechanisms against
  current code, and archive superseded memories with their evidence.
  Current work and task-shaped lessons belong in Beads; memory points to them.
  Review and sanitize private memory before it enters public text.
- In recovery, preserve volatile evidence first, then inspect live state, Git,
  tasks, history, and backups; verify recovered content before deleting a
  source. Load `investigate` when the recovery is ambiguous.
