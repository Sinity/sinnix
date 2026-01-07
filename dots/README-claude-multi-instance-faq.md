# Claude Task Tracking: Multi-Instance FAQ

This document answers critical questions about how Claude's task tracking works with multiple instances, user task separation, and skill awareness.

## The Questions

1. **Multiple Instances** - What happens when multiple Claude instances run at once?
2. **Separation** - How do we distinguish Claude's work from user's personal tasks?
3. **Skill Awareness** - Do new instances know about the skill? What's in their context?
4. **Interaction Patterns** - How should multiple instances coordinate?

---

## 1. Multiple Instances Running at Once

### The Problem

When you have multiple Claude conversations/windows open:
- All instances share the **same** taskwarrior database (`~/.task/`)
- All instances share the **same** timewarrior database (`~/.local/share/timewarrior/`)
- Without coordination, they'll create conflicting or confusing tasks
- Tasks from different conversations will mix together

### The Solution: Instance-Aware Namespacing

Each Claude instance:
1. **Identifies itself** with a unique instance ID
2. **Uses namespaced projects**: `claude.instance.{id}`
3. **Tags everything** with `+instance:{id}`
4. **Checks for other instances** before creating tasks

### Implementation

```bash
# When a new instance starts
CLAUDE_INSTANCE_ID="claude-$(date +%H%M%S)-$$"

# All tasks use this ID
task add "User request: X" \
    project:claude.instance.$CLAUDE_INSTANCE_ID \
    +claude-work \
    +instance:$CLAUDE_INSTANCE_ID

# Time tracking includes instance tag
timew start claude instance:$CLAUDE_INSTANCE_ID conversation "X"
```

### What You'll See

**Scenario: 2 Claude Instances Running**

Instance 1 (terminal window):
```bash
$ task +ACTIVE +instance:claude-032145-12345
ID Description
1  User request: Fix authentication bug
```

Instance 2 (browser window):
```bash
$ task +ACTIVE +instance:claude-032156-67890
ID Description
3  User request: Write documentation
```

Both are in the same database, but clearly separated!

### Coordination Rules

- **Independent work**: Each instance has its own namespace
- **No conflicts**: Instance IDs ensure task separation
- **Awareness**: Each instance can see others' active work
- **Communication**: Instance warns if others are active

---

## 2. Distinguishing Claude Work from User Tasks

### The Problem

You want to use taskwarrior/timewarrior for YOUR OWN tasks too!
- How does Claude know which tasks are yours vs its own?
- Can Claude accidentally modify your tasks?
- Can you see Claude's tasks separately from yours?

### The Solution: Mandatory `+claude-work` Tag

**Rule**: ALL Claude-created tasks MUST have `+claude-work` tag

```
Claude's tasks:  +claude-work tag present
Your tasks:      NO +claude-work tag
```

### Project Hierarchy

```
Taskwarrior Database (shared):

claude/                          ← All Claude work
├── claude.instance.{id}/        ← Specific instance
│   ├── User request: Fix bug
│   └── Research: API docs
├── claude.shared/               ← Shared across instances
│   └── Follow-up: Check tests
└── claude.archive/              ← Completed work

work/                            ← YOUR personal projects
├── Review PR #123
└── Fix production bug

personal/                        ← YOUR personal tasks
├── Buy groceries
└── Call dentist
```

### What Claude CAN Do with Your Tasks

✅ **READ** your tasks
```bash
$ task -claude-work status:pending
# "I see you have 5 tasks due today"
```

✅ **REPORT** on your tasks
```bash
$ task due:today -claude-work
# "You have 3 tasks due today in your 'work' project"
```

✅ **CREATE** tasks FOR you (if you ask)
```bash
User: "Add 'buy milk' to my tasks"
Claude: task add "Buy milk" project:personal  # NO +claude-work tag
```

### What Claude CANNOT Do with Your Tasks

❌ **MODIFY** your tasks without permission
❌ **DELETE** your tasks
❌ **CHANGE** priorities, dates, etc.
❌ **ADD** `+claude-work` tag to your tasks
❌ **TRACK TIME** on your tasks (unless you ask)

### Detection Logic

```bash
# Claude checks before modifying ANY task:
if task {id} export | jq -r '.[0].tags[]?' | grep -q 'claude-work'; then
    # Safe - it's Claude's task
    task {id} modify ...
else
    # STOP - it's user's task, read-only or ask permission
    echo "This is your task. Should I modify it?"
fi
```

### Viewing Tasks Separately

```bash
# Only Claude's work
$ task +claude-work

# Only your tasks
$ task -claude-work

# This instance's work
$ task +instance:$CLAUDE_INSTANCE_ID

# All active work (yours + all Claude instances)
$ task +ACTIVE

# Your pending tasks (excluding Claude)
$ task status:pending -claude-work
```

---

## 3. What New Instances Know About Skills

### The Question

When you launch a new Claude instance, what does it actually know about the task-tracking skill?

### What's in the Initial Context

When a fresh Claude instance starts, it sees:

```
<available_skills>
  <skill>
    <name>task-tracking</name>
    <description>
      Use taskwarrior and timewarrior to track work, model tasks,
      and provide insights during conversations. This skill should
      be invoked proactively whenever starting significant work.
    </description>
    <location>user</location>
  </skill>
</available_skills>
```

That's it! The instance sees:
- ✅ Skill EXISTS
- ✅ Short description
- ✅ Location (user-defined skill)
- ❌ NOT the full 500+ line skill content
- ❌ NOT the detailed patterns and examples
- ❌ NOT the instance coordination rules

### How It Gets the Full Skill

The instance must:

**Option 1: Invoke the skill**
```
Claude uses Skill tool → Full skill content loaded into context
```

**Option 2: Read the skill file**
```bash
Read /realm/project/sinnix/.claude/skills/task-tracking.md
→ Full skill content available
```

**Option 3: `auto_invoke: true` Trigger**
- If the skill has `auto_invoke: true` in frontmatter
- AND the user request matches the trigger pattern
- Claude Code might automatically invoke it

### Current Skill Configuration

```yaml
---
name: task-tracking
description: Use taskwarrior and timewarrior to track work...
trigger: Always active - use proactively during conversations
auto_invoke: true
---
```

With `auto_invoke: true`, the system should proactively invoke the skill when relevant.

### What This Means

**Scenario: You open a new Claude conversation**

1. Instance starts with NO full skill knowledge
2. You ask: "Help me fix this bug"
3. Instance sees "task-tracking" skill in available skills
4. **Either**:
   - Auto-invoke triggers and loads full skill
   - OR Claude explicitly invokes skill
   - OR Claude reads skill file
5. Full guidance becomes available
6. Instance follows patterns (create task, track time, etc.)

### Why This Matters

- **Context efficiency**: Full skill isn't loaded unless needed
- **Flexibility**: Skills can be large, only load when relevant
- **Activation**: You might need to explicitly trigger skill use initially
- **Learning**: Once invoked, instance has full guidance for session

---

## 4. Interaction Patterns

### Pattern 1: Single Instance (Simple)

You're working with one Claude conversation:

```bash
User: "Help me implement dark mode"

Claude:
- Creates: project:claude.instance.claude-session
- Tags: +claude-work +instance:claude-session
- Tracks time: timew start claude instance:claude-session ...
- Works independently
- No coordination needed
```

### Pattern 2: Multiple Independent Conversations

You have 2 Claude windows open for different topics:

**Window 1** (working on frontend):
```bash
Instance ID: claude-032145-12345
Project: claude.instance.claude-032145-12345.frontend
Task: "User request: Implement dark mode"
```

**Window 2** (working on backend):
```bash
Instance ID: claude-032156-67890
Project: claude.instance.claude-032156-67890.backend
Task: "User request: Fix API endpoint"
```

Both instances:
- Work in parallel without conflicts
- Have separate task namespaces
- Track time separately
- Can see each other's work but don't interfere

### Pattern 3: Collaborative Work (Shared Topics)

Two instances working on the same topic:

```bash
# Instance 1 creates a shared task
task add "Research authentication patterns" \
    project:claude.shared.auth \
    +claude-work \
    +shared

# Instance 2 can work on it
task {id} start
# But checks ownership first and coordinates
```

### Pattern 4: Claude + User Personal Tasks

You're using taskwarrior for your own work AND Claude is tracking:

**Your tasks**:
```bash
$ task add "Review PR #123" project:work priority:H
$ task add "Buy groceries" project:personal
$ task add "Prepare presentation" project:work
```

**Claude's tasks** (separate):
```bash
$ task +claude-work
ID Project                          Description
1  claude.instance.claude-session   User request: Help with code
```

**Combined view**:
```bash
$ task status:pending
# Shows BOTH your tasks and Claude's tasks
# But clearly distinguished by project and tags
```

**Filtered views**:
```bash
# Only your work
$ task status:pending -claude-work

# Only Claude's work
$ task +claude-work

# Your work tasks only
$ task project:work -claude-work
```

### Pattern 5: Instance Startup Protocol

When a new instance starts:

```bash
# 1. Check environment
if [ -f "/realm/project/sinnix/.claude/skills/task-tracking.md" ]; then
    # In sinnix, skill is available

    # 2. Check for other instances
    OTHERS=$(task +ACTIVE +claude-work project.startswith:claude.instance count)

    if [ "$OTHERS" -gt 0 ]; then
        echo "⚠ Found $OTHERS other Claude instance(s) active"
        # Use unique instance ID
        INSTANCE_ID="claude-${RANDOM}-$(date +%s)"
    else
        # Simpler ID
        INSTANCE_ID="claude-session"
    fi

    export CLAUDE_INSTANCE_ID="$INSTANCE_ID"
fi

# 3. Create tasks with instance awareness
task add "..." \
    project:claude.instance.$INSTANCE_ID \
    +claude-work \
    +instance:$INSTANCE_ID
```

### Pattern 6: User Asks About Their Tasks

```bash
User: "What tasks do I have due today?"

Claude:
1. Reads tasks: task due:today -claude-work
2. Reports: "You have 3 tasks due today:
   - Review PR #123 (work)
   - Fix production bug (work)
   - Buy groceries (personal)"
3. Does NOT modify or track these tasks
```

### Pattern 7: User Asks Claude to Add Task FOR Them

```bash
User: "Add 'call dentist' to my tasks"

Claude:
1. Creates WITHOUT +claude-work tag:
   task add "Call dentist" project:personal priority:M
2. Confirms: "Added 'Call dentist' to your personal tasks"
3. This task is now YOURS, not Claude's
```

---

## Best Practices Summary

### For Multiple Instances

1. ✅ Each instance uses unique ID
2. ✅ Always tag with `+claude-work` and `+instance:{id}`
3. ✅ Check for other instances at startup
4. ✅ Use namespaced projects
5. ✅ Communicate when other instances detected

### For User/Claude Separation

1. ✅ Claude tasks always have `+claude-work`
2. ✅ User tasks NEVER have `+claude-work`
3. ✅ Check task ownership before modifying
4. ✅ Read user tasks, don't modify without permission
5. ✅ When creating FOR user, omit `+claude-work`

### For Skill Awareness

1. ✅ Understand new instances start with minimal context
2. ✅ Invoke or read skill file when needed
3. ✅ Rely on `auto_invoke: true` for automatic loading
4. ✅ Include startup protocol in skill documentation
5. ✅ Make skill description actionable

### For Coordination

1. ✅ Instance 1 and 2 can work independently
2. ✅ Use `claude.shared.*` for collaborative work
3. ✅ Always check active work before starting
4. ✅ Report multi-instance scenarios to user
5. ✅ Keep instance work cleanly separated

---

## Quick Reference

### Check What's Active

```bash
# My instance's work
task +ACTIVE +instance:$CLAUDE_INSTANCE_ID

# Other Claude instances
task +ACTIVE +claude-work -instance:$CLAUDE_INSTANCE_ID

# All Claude work
task +claude-work

# User's tasks only
task -claude-work

# Everything (user + all Claude instances)
task status:pending
```

### Time Tracking Views

```bash
# My instance's time
timew summary :day instance:$CLAUDE_INSTANCE_ID

# All Claude time
timew summary :day claude

# All time (including user's if they track)
timew summary :day
```

### Project Filters

```bash
# This instance
task project.startswith:claude.instance.$CLAUDE_INSTANCE_ID

# All instances
task project.startswith:claude.instance

# Shared Claude work
task project.startswith:claude.shared

# User work projects
task project:work -claude-work
task project:personal -claude-work
```

---

## The Big Picture

```
┌─────────────────────────────────────────────────────┐
│         Shared Taskwarrior Database                 │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────┐       │
│  │ Claude Instance 1│  │ Claude Instance 2│       │
│  │ +claude-work     │  │ +claude-work     │       │
│  │ +instance:xxx    │  │ +instance:yyy    │       │
│  │ project:claude.*  │  │ project:claude.* │       │
│  └──────────────────┘  └──────────────────┘       │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │          User's Personal Tasks            │     │
│  │          NO +claude-work tag              │     │
│  │          project:work, project:personal   │     │
│  │          READ-ONLY for Claude             │     │
│  └──────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Everything coexists peacefully through:
- **Tagging**: `+claude-work` separates Claude from user
- **Namespacing**: `project:claude.instance.{id}` separates instances
- **Ownership checks**: Verify before modifying any task
- **Coordination**: Instances aware of each other

---

## Troubleshooting

**Q: I see duplicate tasks from different instances**
A: Normal! Each instance tracks its own work. Filter by instance ID if needed.

**Q: Claude modified my task**
A: Should never happen! File a bug. Claude must check for `+claude-work` first.

**Q: Instance ID keeps changing**
A: Expected. Each conversation gets new ID. Use `claude.shared.*` for persistent work.

**Q: How do I see only my work?**
A: `task -claude-work status:pending`

**Q: How do I see all Claude work?**
A: `task +claude-work`

**Q: New instance doesn't seem to use the skill**
A: Explicitly invoke it or trigger with relevant request. Check `auto_invoke` setting.

**Q: Can instances coordinate on the same task?**
A: Yes, use `project:claude.shared.*` and check for locks/annotations.

---

This system allows you to:
- Run multiple Claude instances simultaneously
- Use taskwarrior/timewarrior for your own work
- Keep everything clearly separated and organized
- Have full visibility into what Claude is doing
- Benefit from historical tracking across sessions

It's designed to be **safe**, **transparent**, and **respectful** of your workspace!
