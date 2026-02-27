---
name: task-tracking
description: |
  Use this skill when you need to track work with taskwarrior/timewarrior.
  Triggers: "track this task", "log time", "create a task", "what have we done",
  multi-step work (>3 tool calls), significant user requests.
---

# Task and Time Tracking with Taskwarrior

Use taskwarrior and timewarrior to track work during conversations. This provides visibility into what was accomplished and how long it took.

## When to Track

**Create tasks for:**

- User requests (tag: `+user_request`)
- Multi-step work (>3 tool calls or >5 minutes)
- Research and investigation (tag: `+research`)
- Follow-up items (tag: `+follow_up`)

**Track time on:**

- All significant work (>2 minutes)
- Use tags: `agent`, `agent_${AGENT_NAME}`, `session_${AGENT_SESSION_ID}`, `{activity}`

## Setup

```bash
# Set identity at session start
export AGENT_NAME="claude"  # or codex, gemini, etc.
export AGENT_SESSION_ID="${AGENT_NAME}-$(date +%H%M%S)-$$"

# Load helpers
source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh
```

## Core Operations

### Track a User Request

```bash
agent_track_request "Description of work" "30min" "H"
# Creates task + starts timer
# Priority: H (high), M (medium), L (low)
```

### Annotate Current Work

```bash
agent_annotate "Found issue with X"
agent_annotate "Completed step 1"
```

### Complete a Task

```bash
agent_complete_task {id} "actual-time"
# Marks task done + stops timer
```

### Check Status

```bash
agent_status           # Current session status
agent_session_summary  # Full session summary
```

## Project Namespacing

All agent tasks use `project:agent.*` hierarchy:

```
agent.${AGENT_NAME}.${AGENT_SESSION_ID}   <- This session's work
agent.shared.${topic}                     <- Shared across sessions
{anything-else}                           <- User tasks (READ-ONLY)
```

## Critical Rules

1. **All agent tasks must have `+agent` tag**
2. **Never modify user tasks** (tasks without `+agent` tag)
3. **Verify ownership before modifying**: `agent_owns_task {id}`
4. **Session IDs prevent conflicts** between concurrent sessions

## Viewing Tasks

```bash
# This session's tasks
task project:agent.$AGENT_NAME.$AGENT_SESSION_ID

# All active agent tasks
task +ACTIVE +agent

# User's tasks (read-only)
task -agent
```

## Example Session

```bash
# 1. Setup
export AGENT_NAME="claude"
source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh

# 2. Track user request
agent_track_request "Implement authentication feature" "1h" "H"
# Output: ✓ Tracking request as task 42 (claude/claude-143022-12345)

# 3. Annotate progress
agent_annotate "Designed JWT flow"
agent_annotate "Implemented token generation"

# 4. Complete
agent_complete_task 42 "45min"
```

## References

- `references/quickstart.md` - terse command-first flow for daily usage
- `references/extended.md` - extended conventions and troubleshooting
