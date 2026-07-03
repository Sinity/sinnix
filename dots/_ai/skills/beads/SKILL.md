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
