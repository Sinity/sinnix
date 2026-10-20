# Operator environment

These rules apply across repositories. Each repository's `AGENTS.md` owns its
project rules; runtime and task state stay with their owning tools.

## Writing

- Lead with the useful result or concrete information. Use plain, precise
  wording; cut padding and generic promises about your process.
- Omit unsolicited negatives, defensive caveats, and claims about how careful,
  safe or rigorous you will be. State the relevant facts instead.
- Include a caveat when it changes interpretation, a decision, risk or the next
  action. Make it short and specific. Preserve material uncertainty, accuracy
  and required confirmations; useful negation is fine.
- In drafts, preserve the requested meaning without inventing claims or
  commitments for the user.

Illustrative examples:

- "I won't confuse an organized archive with benefit eligibility."
  → "The archive is organized." Omit the eligibility comparison when irrelevant.
- "I'll be careful not to assume the records are complete."
  → "Coverage ends in August." State the actual limitation when it matters.

## Work

- Carry authorized work to a verified result. Compaction continues the work; it
  is not a deadline or a reason to defer.
- A request to inspect, diagnose, or advise authorizes read-only checks. A
  request to improve or implement authorizes scoped changes and their normal
  verification. Ask only when authority, an irreversible consequence, or the
  intended outcome is genuinely ambiguous.
- State scope and exclusions for multi-step work. Follow discoveries that
  affect the outcome; record the rest without widening the task.
- Separate observations, inferences, and unverified claims. When blocked,
  name the missing evidence.
- Change connected callers and docs together. Probe concrete uncertainties;
  verify once the change is coherent.
- Fix cheap, understood nearby defects with proportionate checks and a brief
  note. Separate work that needs substantial investigation, new dependencies,
  conflicting ownership, or material delay. Keep unfinished scope and failures visible.
- When a replacement ships, remove its predecessor and connected callers,
  commands, docs, and tests. Deleting unfinished code needs a shipped
  replacement, recorded retirement, or explicit authorization.
- Preserve unrelated edits. Before destructive recovery, resolve the exact
  targets, preserve recoverable evidence, and state the intended action.

## Reporting and durable text

Load `writing-style` for prose people read and `writing-for-agents` for
instructions, skills, and memory.

- Report the outcome, changed files, exact verification, and residual risk.
  Keep progress updates short.
- Write each fact once, where it is owned: comments hold constraints, docs hold
  current behavior, Beads hold problems, decisions, and evidence. Incident
  history belongs in its task, never in always-loaded instructions.
- Read exit statuses directly. Capture large output for inspection; never
  infer verification success from `tail` or another pipeline's final status.
- Before compaction or stopping mid-work, leave a handoff, and on re-entry
  verify the live facts needed for the next action. Load `handoff` for the
  compact current-state note; do not reread unchanged records routinely.

## Filesystem and private data

Host `sinnix-prime`. Root storage is wear-limited; heavy work belongs on
`/realm`.

- `/realm/project/<subject>/repo/`: active repositories.
  `/realm/worktree/`: isolated checkouts and compile-heavy work.
- `/realm/`: subject folders and service storage; read `/realm/INVENTORY.md`
  and mutate through the owning tools. `/realm/state/`: live service state and
  the external Beads databases.
- `/realm/tmp/work/` is the managed `$TMPDIR`. Put scratch in a per-task
  subdirectory and remove it when done; retained results go to their owning
  store. `/tmp` is a small tmpfs.
- In unattended work, give `rm` literal absolute paths and use `git -C <path>`,
  `env -C <dir> <cmd>`, or absolute paths instead of `cd <dir> && …`; Claude
  Code stops for a person otherwise. The working directory may reset between
  tool calls, so a check meant for a worktree names it explicitly.
- Home Manager rebuilds `$HOME`; edit the declared source of a managed file.
  `xdg-user-dir` gives user-facing download and document locations.

Tracked files, commits, task exports, CI logs, and PR text are public. Keep
secrets, captures, transcripts, personal databases, and private analyses out of
them; test fixtures stay synthetic and neutral.

## Runtime

Load `agent-runtime` before AgentCTL job or history work and `orchestrate` before
running agents in parallel.

- State lives with its owners (pueue, Git and worktrunk, GitHub, Beads,
  systemd); `agentctl` is a CLI over them. Reconcile those sources rather than
  keeping another ledger.
- Short foreground checks run directly. Queued, heavy, detached, or shared work
  runs as a declared operation:
  `agentctl job start <project> <operation> [options] [-- <declared args>]`.
  Take syntax from `agentctl <verb> --help` and
  `/realm/project/sinnix/repo/docs/agentctl.md`. On an error, read the message and
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
- The author reviews the coherent change and uses a focused import, static
  check, or discriminating test when useful. After fixes, revisit the delta
  and affected invariants. Broaden checks at integration milestones or for a
  concrete risk. Preserve required CI checks and assertions; report failures
  and untested areas. Known failures need not block unrelated work.
- A second reviewer needs a named unresolved question. Stage explicit paths;
  preserve hooks and branch protection.
- Where a forge runs a hosted reviewer on PRs, that review is the independent
  review; add a reviewer agent only for a named risk it cannot cover. Answer
  findings with a fix or a concrete refutation. Follow the repository's actual
  required statuses and review-resolution rules. Where the forge enforces these,
  merge with
  `gh pr merge --auto --squash --match-head-commit <sha>` and let it gate.
  File substantial out-of-scope or post-merge findings as follow-up work.
- A partial delivery leaves its unmet acceptance criteria open.

## Desktop and host changes

- The operator's Chrome is shared. Check `sinnix-chrome-control status`, and
  retry and inspect `list-tabs` before concluding it is unavailable. Agent work
  uses its own agent window or background tab by page ID; the operator's tabs
  are touched only when a request is about them. Load `desktop-control`
  for browser, Kitty, Hyprland, and screenshot work. `sinnix-observe` gives live
  host evidence.
- Sinnix activation changes the live machine; follow the Activation section of
  `/realm/project/sinnix/repo/AGENTS.md`. An edited source proves nothing about
  what is installed.
- Resets, deployment, paid vector preservation, and data-loss risks require
  evidence appropriate to their consequence. Keep those checks at the actual
  operational boundary rather than applying them to every source patch.

## History and memory

- Session history: Polylogue, or `claude-sessions` for raw Claude transcripts.
  Cross-source history: Lynchpin. Host evidence: the runtime inventory,
  `sinnix-observe`, `/realm/activity/`, `/realm/device/sinnix-prime/`. Operator stream:
  `/realm/personal/journal/raw-log.md`.
- Project memory (`~/.claude/projects/<project>/memory/MEMORY.md`) indexes
  stable facts and pointers. Verify recalled mechanisms against current code;
  archive superseded memories with their evidence. Beads owns current work
  and task lessons. Sanitize private memory before using it in public text.
- In recovery, preserve volatile evidence first, then inspect live state, Git,
  tasks, history, and backups; verify recovered content before deleting a
  source. Load `investigate` when the recovery is ambiguous.
