---
name: task-tracking
description: Agent-agnostic taskwarrior/timewarrior reference with streamlined conventions.
trigger: When you need detailed examples or complex scenarios
auto_invoke: false
---

# Task & Time Tracking (Agent-Agnostic)

Core rules live in `/realm/project/sinnix/dots/ai/instructions/AGENTS.md`.
This file provides extended examples and troubleshooting.

## Identity

```bash
export AGENT_NAME="codex"  # or claude, gemini, etc.
export AGENT_SESSION_ID="${AGENT_SESSION_ID:-${AGENT_NAME}-$(date +%H%M%S)-$$}"
```

## Naming & Tagging

**Projects**

- Session: `agent.${AGENT_NAME}.${AGENT_SESSION_ID}`
- Shared: `agent.shared.${topic}`

**Tags**

- Agent tasks: `+agent`
- Semantic tags: `+user_request`, `+research`, `+follow_up`, `+coding`, `+documentation`, `+review`

**Timewarrior tags**

- `agent`
- `agent_${AGENT_NAME}`
- `session_${AGENT_SESSION_ID}`
- activity tag (`conversation`, `research`, `coding`, ...)

## Core Helper Commands

```bash
source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh

agent_track_request "User asked for X" "30min" "H"
agent_annotate "Found Y in logs"
agent_complete_task {id} "45min"
agent_status
agent_session_summary
```

## Direct Usage

```bash
task add "User request: {desc}" \
  project:agent.$AGENT_NAME.$AGENT_SESSION_ID \
  priority:H \
  estimate:30min \
  tags:agent,user_request

timew start agent agent_${AGENT_NAME} session_${AGENT_SESSION_ID} conversation
```

## Common Workflows

**Research**

```bash
task add "Research: {topic}" \
  project:agent.$AGENT_NAME.$AGENT_SESSION_ID \
  estimate:30min \
  tags:agent,research
```

**Follow-up**

```bash
task add "Follow-up: {item}" \
  project:agent.shared.{topic} \
  wait:later \
  tags:agent,follow_up
```

**Subtask**

```bash
task add "{subtask}" \
  project:agent.$AGENT_NAME.$AGENT_SESSION_ID \
  depends:{parent_id} \
  tags:agent
```

## Ownership Checks

```bash
task {id} export | jq -r '.[0].project // ""' | grep -q '^agent\.'
```

If the project is not `agent.*`, treat it as user-owned.

## Multi-Session Coordination

```bash
task +ACTIVE +agent project.startswith:agent.$AGENT_NAME.
task project:agent.$AGENT_NAME.$AGENT_SESSION_ID
```

## Troubleshooting

- **Tag parse errors**: use `tags:` in task add and avoid hyphens in tag names.
- **Timew mix-ups**: ensure `session_${AGENT_SESSION_ID}` is included and avoid passing descriptions as tags.
- **Ownership confusion**: check the `project` field, not just tags.

## Anti-Patterns

- Creating agent tasks without `+agent`
- Storing agent tasks outside `project:agent.*`
- Editing user tasks without explicit permission
