# Agent Task Tracking (Streamlined)

This repo uses an agent-agnostic workflow for Taskwarrior/Timewarrior.
Canonical rules are in `/realm/project/sinnix/dots/ai/instructions/AGENTS.md`.

## Quick Start

```bash
export AGENT_NAME="codex"  # or claude, gemini, etc.
export AGENT_SESSION_ID="${AGENT_SESSION_ID:-${AGENT_NAME}-$(date +%H%M%S)-$$}"
source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh

agent_track_request "User request" "30min" "H"
```

## Key Rules

- Agent tasks **must** have `+agent` and `project:agent.*`.
- User tasks are anything without the `+agent` tag.
- Time tracking uses tags: `agent`, `agent_${AGENT_NAME}`, `session_${AGENT_SESSION_ID}`, plus activity tags.

## Common Commands

```bash
agent_status
agent_session_summary
agent_followup "Verify after reboot"
task -agent status:pending  # user tasks
```

## Files

- Helpers: `/realm/project/sinnix/dots/taskwarrior/agent-helpers.sh`
- Core protocol: `/realm/project/sinnix/dots/ai/instructions/AGENTS.md`
