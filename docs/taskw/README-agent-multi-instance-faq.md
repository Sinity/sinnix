# Agent Task Tracking: Multi-Session FAQ

This document covers how multiple agent sessions share Taskwarrior/Timewarrior safely.

## Why sessions matter

Taskwarrior and Timewarrior share a single database. Sessions must use namespaced
projects to avoid collisions.

## How sessions are named

- Session project: `agent.${AGENT_NAME}.${AGENT_SESSION_ID}`
- Shared project: `agent.shared.${topic}`

## Agent vs user tasks

- Agent tasks must include `+agent` and `project:agent.*`.
- User tasks are anything without the `+agent` tag.
- Never modify user tasks without explicit permission.

## Ownership check before edits

```bash
task {id} export | jq -r '.[0].project // ""' | grep -q '^agent\.'
```

If the project does not start with `agent.`, treat it as user-owned.

## Useful commands

```bash
# This session
task project:agent.$AGENT_NAME.$AGENT_SESSION_ID

# Other active sessions (same agent name)
task +ACTIVE +agent project.startswith:agent.$AGENT_NAME.

# User tasks only (read-only)
task -agent status:pending
```

## Time tracking

Use tags only (no descriptions):
```
agent agent_${AGENT_NAME} session_${AGENT_SESSION_ID} {activity}
```

## What new sessions know

`AGENTS.md` is always loaded at startup. The task-tracking skill and README
files are optional references and must be read explicitly when needed.
