# Task & Time Tracking (Expanded Reference)

This file supplements `/realm/project/sinnix/dots/ai/instructions/AGENTS.md`.
Core protocol lives there; follow it first.

## Quick Start

```bash
export AGENT_NAME="codex"  # or claude, gemini, etc.
export AGENT_SESSION_ID="${AGENT_SESSION_ID:-${AGENT_NAME}-$(date +%H%M%S)-$$}"

source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh

agent_track_request "What the user asked" "30min" "H"
```

## Common Patterns

**Create a follow-up**
```bash
agent_followup "Verify scratchpad behavior after reboot"
```

**See user tasks (read-only)**
```bash
task -agent status:pending
```

**Time tracking tags**
```
agent agent_${AGENT_NAME} session_${AGENT_SESSION_ID} {activity}
```
Timewarrior uses tags only; do not pass task descriptions as tags.

## Anti-Patterns

- Creating tasks without the `+agent` tag
- Using non-`agent.*` projects for agent work
- Modifying user tasks without explicit permission
