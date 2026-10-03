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
- Work in coherent batches, including connected callers and docs. Use a quick
  probe to settle a concrete uncertainty; verify when the change is coherent.
- Fix cheap, well-understood related or nearby defects while context is loaded,
  with proportionate checks and a brief note. No separate ticket, plan, or
  review cycle for a small correction. Separate work only for substantial
  investigation, new architectural dependencies, conflicting ownership, or
  material delivery delay. Keep remaining failures and unfinished scope visible.
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
- Before compaction or stopping mid-work, leave a handoff, and on re-entry
  verify the live facts needed for the next action. Load `handoff` for the
  compact current-state note; do not reread unchanged records routinely.

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
- Claude Code asks a person before running, even in bypass mode, any `rm`
  whose target it cannot resolve statically (a shell variable, a glob after
  `cd`) and any compound command that changes directory and then writes. In
  unattended work, give `rm` literal absolute paths and use `git -C <path>`,
  `env -C <dir> <cmd>`, tool options, or absolute paths instead of
  `cd <dir> && …`. The shell's working directory may reset between tool
  calls, so a check meant for a worktree must name it explicitly.
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
- For ordinary fixes, briefly review the actual delta and use a cheap import,
  static check, or small discriminating test when useful. Run broader regression
  at integration milestones or for a concrete risk, not after every patch.
  Preserve required CI checks and assertions. Report failures and untested
  areas honestly; ordinary known reds need not block unrelated work.
- The author owns correctness review. Review a coherent delivery once, then
  review changed deltas and affected invariants after fixes. Use project guides
  for relevant risks; no narrated per-item checklist or restart from the top.
  A second reviewer needs a named unresolved question. Stage explicit paths.
  Never bypass hooks or branch protection.
- Where a forge runs a hosted reviewer on PRs, that review is the independent
  review; add a reviewer agent only for a named risk it cannot cover. Answer
  findings with a fix or a concrete refutation. Follow the repository's actual
  required statuses and review-resolution rules. Where the forge enforces these,
  merge with
  `gh pr merge --auto --squash --match-head-commit <sha>` and let it gate.
  Substantial findings outside this delivery or arriving after a merge become
  a follow-up; cheap nearby corrections belong in the current work.
  For Codex, review state is the Code Review row of its summary comment; its
  separate security-review usage-limit notice is unrelated.
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
- Resets, deployment, paid vector preservation, and data-loss risks require
  evidence appropriate to their consequence. Keep those checks at the actual
  operational boundary rather than applying them to every source patch.

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
