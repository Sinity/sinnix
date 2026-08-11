---
name: beads
description: Use when a repository has a Beads workspace (`.beads/`) or the user asks to find ready work, claim or close tasks, create follow-up issues, inspect blockers, record durable project memory, or recover task context across Claude/Codex sessions.
---

# Beads

Use `bd` as the durable project task system when the repository has an active Beads workspace. Local plans are still useful for the current turn; Beads is for shared task state, blockers, dependencies, follow-up work, and handoff.

## First Step

Run:

```bash
bd prime
```

If that fails or prints no useful context, check workspace resolution:

```bash
bd where
```

## Workflow

1. Find available work:

```bash
bd ready --json
```

2. Inspect before editing:

```bash
bd show <id> --json
```

3. Claim work atomically when taking ownership:

```bash
bd update <id> --claim --json
```

4. Create durable follow-up work when implementation reveals new tasks:

```bash
bd create "Short title" --description="Why this exists and what needs to be done" --type=task --priority=2 --json
```

5. Close only when the requested work is actually complete:

```bash
bd close <id> --reason="Completed" --json
```

## Rules

- Prefer `--json` when parsing output programmatically.
- Do not use `bd edit`; it opens an interactive editor. Use `bd update` flags.
- Link discovered follow-up work with Beads dependencies when there is a parent task.
- Treat `bd dolt push` like `git push`: allowed when the repository/user/orchestrator policy authorizes pushing, but do not bypass default-branch or PR rules.
- Repository instructions override generic Beads template text.

## Hazards (branch switching, worktrees, commit cadence)

These are bd's by-design sync semantics colliding with branch-heavy workflows —
not bugs, but they will silently revert or stale your view of bead state.

- **Every `bd` invocation reimports the invoking checkout's committed
  `.beads/issues.jsonl` into the shared DB** — including plain read-only calls
  like `bd show`. A bead closed on branch A reads back as open on branch B if
  B forked from an older master; nothing is lost (the close is in git
  history), but `bd show`/`bd ready` output is stale until a commit carrying
  that state lands on the current branch.
- The same reimport fires from **aging worktrees**: a worktree frozen at an
  older commit can time-machine live bead state over a coordinator's
  concurrent writes, even from a lane that never touches beads intentionally
  (confirmed repeatedly, polylogue 2026-08-01: 5+ coordinator closes reverted
  in one session). **Lane agents dispatched into worktrees make no `bd`
  writes at all**; the coordinator audits bead state (diff expected vs
  `bd show --json`) at merge-train boundaries and re-applies anything
  reverted, rather than trusting a single write to have stuck.
- Mitigations for branch churn: don't open a new `chore(beads):` branch while
  one is open — merge or extend it; merge bd-only bookkeeping branches
  immediately; fold a `bd claim`/`close` into the same branch as the code
  change it accompanies; re-verify with `bd show <id> --json` after any
  checkout/merge/worktree-add before trusting query output for a bead you
  just touched.
- **`.beads/*.jsonl` merge conflicts**: `bd export` resolves its output path
  from bd's own database location, independent of cwd — inside a temporary
  conflict-resolution worktree it silently no-ops on that worktree's own
  file, leaving literal conflict markers in place. Instead extract both sides
  (`git show :2:.beads/issues.jsonl` / `:3:...`), hand-merge bead-by-id
  preferring the later `updated_at`, verify every line parses as JSON, then
  `git add`.
- **Batch `.beads/issues.jsonl` commits per unit of work, not per bd
  operation.** `bd export` re-derives the full jsonl regardless of how many
  bd calls preceded it, so batching costs nothing: do every bd write for one
  coherent unit (a triage pass, closing every bead landed by a merge train,
  one fanout wave's findings), then one commit summarizing the batch. A
  5-hour session once produced ~85 separate `chore(beads):` commits — one
  per operation — drowning real work in the log (polylogue 2026-08-03). A
  submodule split is not the fix; commit cadence is.
