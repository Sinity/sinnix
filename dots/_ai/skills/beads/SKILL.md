---
name: beads
description: Use when a repository has a Beads workspace (`.beads/`) or the user asks to find ready work, claim or close tasks, create follow-up issues, inspect blockers, record durable project memory, or recover task context across Claude/Codex sessions.
---

# Beads

AgentCTL is the normal task client for registered projects. Its `task` CLI and `agent-control` MCP routes carry task state through the canonical Beads backend. Local plans are still useful for the current turn; Beads remains the durable task substrate for shared state, blockers, dependencies, follow-up work, and handoff.

## Task authority

Use AgentCTL for task operations:

```bash
agentctl task list <project>
agentctl task get <project> <task>
agentctl task claim <project> <task> --request-id <id>
```

Use `bd where --json` only when investigating the backend authority itself:

```bash
bd where
```

## Rules

- Coding workers do not perform task bookkeeping. The coordinator owns AgentCTL task mutations and durable follow-up creation.
- AgentCTL task mutations require their stable request ID. Read task state through AgentCTL rather than checkout JSONL.
- Repository instructions override this generic skill.

## Authority, worktrees, and exports

AgentCTL binds each registered project to its canonical external Beads backend. Worktree JSONL is an export artifact, never task authority. Its path and database are only relevant when an operator is diagnosing the backend through `bd where --json`.
