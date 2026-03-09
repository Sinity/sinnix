---
name: recap
description: Quick context refresh - reduce cognitive load during sessions
triggers:
  - "what were we doing"
  - "where are we"
  - "remind me"
  - "recap"
  - "summarize session"
allowed-tools:
  - Read
argument-hint: "[status|decisions|timeline|handoff]"
---

# Session Recap

Quick cognitive offload for current conversation. Pick what you need:

**Arguments**: $ARGUMENTS

---

## Capabilities

### Status (default)

Where we are right now:

- Current task/focus
- What's done
- What's pending/blocked

### Decisions

Key choices made this session:

- What was decided
- Why (if discussed)
- Alternatives rejected

### Timeline

Chronological progression:

- What we started with
- Major steps taken
- Where we ended up

### Handoff

Prepare for session end:

- Accomplishments summary
- Unfinished work
- Suggested next steps
- Worth remembering (for CLAUDE.md or scratch)

---

## Output Style

Be concise. Bullet points. No fluff. If something's unclear from context, say so rather than guessing.
