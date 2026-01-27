# Task Tracking Architecture (Agent)

## Goals

- Always-on core rules.
- Optional deep references when needed.
- Minimal context overhead for new sessions.

## Layers and Files

```
AGENTS.md (always loaded)
└─ Core protocol: identity, ownership checks, required tags/projects

Dots reference (on demand)
├─ dots/ai/instructions/task-tracking.md
└─ .claude/skills/task-tracking.md

User docs (on demand)
├─ dots/README-agent-task-tracking.md
└─ dots/README-agent-multi-instance-faq.md

Helpers
└─ dots/taskwarrior/agent-helpers.sh
```

## Why AGENTS.md

Skills are not guaranteed to load on startup. AGENTS.md is always injected into
context, so baseline behavior is consistent across sessions and agents.

## Verification Checklist

1. Start a fresh session and confirm AGENTS.md content is present.
2. Run `agent_track_request` and verify:
   - `project:agent.${AGENT_NAME}.${AGENT_SESSION_ID}`
   - `+agent` tag is set
3. Run `timew summary :day session_${AGENT_SESSION_ID} :tags` to confirm tags.
4. Run `task -agent status:pending` to confirm user tasks stay separate.
