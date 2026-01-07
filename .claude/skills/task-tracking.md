---
name: task-tracking
description: Detailed reference guide for taskwarrior/timewarrior usage patterns, workflow examples, and advanced coordination scenarios. Core protocol is in CLAUDE.md.
trigger: When you need detailed examples or complex scenarios
auto_invoke: false
---

# Task & Time Tracking - Detailed Reference

**Note**: Core operational protocol is in `/realm/project/sinnix/CLAUDE.md` and is ALWAYS active.

This skill provides:
- Detailed workflow patterns and examples
- Advanced multi-instance coordination scenarios
- Comprehensive command reference
- Troubleshooting guides
- Best practices and anti-patterns

For basic usage, refer to CLAUDE.md. Use this skill for deep dives and complex scenarios.

## Instance Awareness

**CRITICAL**: When starting a new conversation:
1. Check if you're part of a multi-instance environment
2. Identify yourself with a unique instance ID
3. Use instance-specific project namespacing
4. Check for active work by other instances

```bash
# At conversation start, identify yourself
INSTANCE_ID="claude-$(date +%s)-$$"
export CLAUDE_INSTANCE_ID="$INSTANCE_ID"

# Check for other active instances
task +ACTIVE project.startswith:claude.instance
```

## Separation of Concerns

### Claude Work vs User Work

**Claude's Tasks**: `project:claude` or `project:claude.*`
- All work Claude does tracking conversations
- Tagged with `+claude-work`
- Namespaced by instance when needed

**User's Tasks**: `project:` anything else OR no `+claude-work` tag
- User's personal task management
- Never modified by Claude
- Claude can read/report but not change

### Project Hierarchy

```
claude                           # Root for all Claude work
├── claude.instance.{id}         # Specific instance work
│   ├── claude.instance.{id}.conversation
│   └── claude.instance.{id}.research
├── claude.shared                # Shared across instances
│   ├── claude.shared.documentation
│   └── claude.shared.analysis
└── claude.archive               # Completed work

{user-projects}                  # User's personal projects (untouched)
├── work
├── personal
└── ...
```

## Core Principles

1. **Track Everything**: Create tasks for user requests, subtasks, follow-ups, and discoveries
2. **Time All Work**: Start time tracking when beginning significant work (>2 minutes)
3. **Context Awareness**: Use proper tags, projects, and UDAs to model work accurately
4. **Instance Isolation**: Keep instance work separate unless explicitly shared
5. **User Respect**: Never modify user's tasks
6. **Provide Insights**: Periodically share summaries and progress reports
7. **Continuous Learning**: Use historical data to improve estimates and planning

## Multi-Instance Coordination

### Instance Startup Protocol

When a new conversation starts:

```bash
# 1. Identify yourself
INSTANCE_ID="claude-conversation-$(date +%H%M%S)"

# 2. Check for active work
task +ACTIVE project.startswith:claude.instance

# 3. If other instances are active, namespace yourself
# 4. If resuming work, use existing instance ID
# 5. Otherwise, use shared project for general work
```

### Coordination Patterns

**Scenario 1: Independent Conversations**
- Each instance uses `project:claude.instance.{id}`
- No coordination needed
- Time tracking tagged with instance ID

**Scenario 2: Collaborative Work**
- Use `project:claude.shared.{topic}`
- Check for task locks before modifying
- Coordinate via task annotations

**Scenario 3: User Running Personal Tasks**
- Claude NEVER modifies tasks without `+claude-work` tag
- Can read and report: "I see you have 5 tasks due today"
- Can create tasks FOR user if explicitly asked: "Please add X to my tasks"

## When to Create Tasks

### ALWAYS Create Tasks For:

- **User Requests** - Any explicit request from the user
  ```bash
  task add "User request: {description}" \
    project:claude.instance.{id} \
    priority:H \
    +user-request \
    +claude-work
  ```

- **Multi-Step Work** - Anything requiring >3 tool calls or >5 minutes
  ```bash
  task add "{description}" \
    project:claude.instance.{id}.{topic} \
    estimate:{time} \
    complexity:{level} \
    energy:{level} \
    +claude-work
  ```

- **Follow-Up Items** - Things to check, verify, or complete later
  ```bash
  task add "{item}" \
    project:claude.shared \
    +follow-up \
    +claude-work \
    wait:later
  ```

- **Discovered Issues** - Bugs, problems, or improvements found during work
  ```bash
  task add "Issue: {description}" \
    project:{current} \
    priority:M \
    +bug \
    +claude-work
  ```

- **Research/Investigation** - When exploring codebases or documentation
  ```bash
  task add "Research: {topic}" \
    project:claude.instance.{id} \
    +research \
    +claude-work
  ```

### Task Metadata Guidelines

**Projects**: Use hierarchical naming with instance awareness
- `claude.instance.{id}` - Instance-specific work
- `claude.instance.{id}.{topic}` - Specific topic within instance
- `claude.shared.{topic}` - Shared across instances
- `claude.archive` - Completed historical work

**Tags**: Use semantic tags PLUS Claude identification
- `+claude-work` - **REQUIRED** on all Claude tasks
- `+instance:{id}` - Specific instance identification
- `+user-request` - Direct user request
- `+follow-up` - Needs follow-up
- `+research` - Research/investigation
- `+bug` - Bug or issue
- `+improvement` - Improvement idea
- `+documentation` - Documentation work
- `+testing` - Testing work
- `+review` - Needs review
- `+shared` - Shared work across instances

**UDAs**: Track estimates and actuals
- `estimate:30min` - Estimated effort
- `energy:high` - Required energy level
- `complexity:moderate` - Complexity assessment
- `impact:high` - Impact level

**Priority**: Use meaningfully
- `H` - Blocking or urgent
- `M` - Important but not blocking
- `L` - Nice to have

## When to Track Time

### START Time Tracking When:

1. **Beginning Significant Work** (>2 minutes expected)
   ```bash
   timew start claude instance:{id} {project} {tags} "{description}"
   ```

2. **Starting a Task**
   ```bash
   task {id} start
   timew start claude instance:{id} {project} {tags} "{task description}"
   ```

3. **Context Switching** - Stop previous, start new
   ```bash
   timew stop
   timew start claude instance:{id} {new-context} "{description}"
   ```

### Time Tracking Tags

Use consistent tags with Claude identification:
- `claude` - **REQUIRED** on all Claude time entries
- `instance:{id}` - Instance identification
- `coding` - Writing code
- `debugging` - Debugging issues
- `research` - Researching/investigating
- `documentation` - Writing docs
- `planning` - Planning and design
- `review` - Reviewing code/work
- `learning` - Learning new things
- `testing` - Testing functionality
- `conversation` - Active conversation work

## Respecting User's Task Space

### What Claude CAN Do:

✅ **Read** user's tasks
```bash
task project.not:claude status:pending
```

✅ **Report** on user's tasks
```
"I see you have 5 tasks due today in your 'work' project"
```

✅ **Create tasks FOR user** if explicitly asked
```bash
# User says: "Add 'buy milk' to my tasks"
task add "Buy milk" project:personal  # NO +claude-work tag
```

### What Claude MUST NOT Do:

❌ **Modify** user's tasks without explicit permission
❌ **Delete** user's tasks
❌ **Change** user's task priorities/dates/etc
❌ **Track time** on user's behalf (unless asked)
❌ **Add** `+claude-work` to user's tasks

### Detection Pattern:

```bash
# Is this a Claude task?
if task {id} export | jq -r '.[0].tags[]?' | grep -q 'claude-work'; then
    # YES - Claude can modify
else
    # NO - User's task, read-only or ask permission
fi
```

## Instance Detection at Startup

When invoked, immediately check context:

```bash
# Check if we're in sinnix
if [ -f "/realm/project/sinnix/.claude/skills/task-tracking.md" ]; then
    SKILL_ACTIVE=true

    # Check for other active instances
    ACTIVE_INSTANCES=$(task +ACTIVE +claude-work project.startswith:claude.instance count 2>/dev/null || echo "0")

    if [ "$ACTIVE_INSTANCES" -gt 0 ]; then
        echo "Note: $ACTIVE_INSTANCES other Claude instance(s) active"
        # Use unique instance ID
        INSTANCE_ID="claude-${RANDOM}-$(date +%s)"
    else
        # Can use simpler naming
        INSTANCE_ID="claude-session"
    fi

    export CLAUDE_INSTANCE_ID="$INSTANCE_ID"
fi
```

## Updated Workflow Patterns

### Pattern 1: User Makes Request (Instance-Aware)

```bash
# 1. Create task for request with instance ID
task add "User request: {description}" \
    project:claude.instance.$CLAUDE_INSTANCE_ID \
    priority:H \
    +user-request \
    +claude-work \
    +instance:$CLAUDE_INSTANCE_ID \
    estimate:{time}

# 2. Start time tracking with instance tag
timew start claude instance:$CLAUDE_INSTANCE_ID conversation user-request "{description}"

# 3. Break into subtasks if complex
task add "Subtask: {step1}" \
    project:claude.instance.$CLAUDE_INSTANCE_ID.{topic} \
    depends:{parent-id} \
    +claude-work

# 4. Work on each subtask
task {id} start
# ... do work ...
task {id} done

# 5. Complete parent task
task {parent-id} done
timew stop
```

### Pattern 2: Checking User's Tasks (Read-Only)

```bash
# User asks: "What do I have due today?"

# Read user's tasks (NOT claude-work)
task due:today -claude-work

# Report to user
"You have 3 tasks due today:
- Fix authentication bug (work project)
- Review pull request (work project)
- Buy groceries (personal project)"
```

### Pattern 3: Creating Task FOR User

```bash
# User says: "Add 'call dentist' to my tasks"

# Create WITHOUT +claude-work tag
task add "Call dentist" project:personal priority:M

# Confirm
"Added 'Call dentist' to your personal tasks"
```

### Pattern 4: Multi-Instance Awareness

```bash
# When starting work, check for others
OTHERS=$(task +ACTIVE +claude-work project.startswith:claude.instance -instance:$CLAUDE_INSTANCE_ID count)

if [ "$OTHERS" -gt 0 ]; then
    # Let user know
    "Note: I see another Claude instance is working on {task from other instance}"
    # Use unique namespace to avoid conflicts
fi
```

## Proactive Usage Triggers

### MUST Use When:

1. **User says "help me with X"** → Create task, start tracking
2. **Starting to write code** → Start task + time tracking with instance ID
3. **Beginning investigation** → Create research task with +claude-work
4. **User mentions future work** → Create follow-up task in shared project
5. **Discovering complexity** → Update task estimate, add subtasks
6. **Completing significant work** → Mark task done, stop tracking, update actual time
7. **Natural break point** → Provide summary of tasks/time

### Instance Coordination Check:

Before ANY modification to tasks:
```bash
# Check if task is ours
if task {id} export | jq -r '.[0].tags[]?' | grep -q "instance:$CLAUDE_INSTANCE_ID\|claude-work"; then
    # Safe to modify
else
    # Either user's task or another instance's - ask permission
fi
```

## Reporting and Insights

### Proactive Reports (Instance-Scoped)

**Quick Status**:
```bash
task +ACTIVE +instance:$CLAUDE_INSTANCE_ID
timew
```

**Session Summary** (only this instance):
```bash
task end.after:today +claude-work +instance:$CLAUDE_INSTANCE_ID status:completed
timew summary :day instance:$CLAUDE_INSTANCE_ID
```

**All Claude Work** (all instances):
```bash
task +claude-work status:completed end.after:today
timew summary :day claude
```

**User's Work** (separate reporting):
```bash
task -claude-work status:pending
# Report but don't modify
```

## Best Practices

1. **Always Tag +claude-work** - Every Claude-created task
2. **Use Instance IDs** - When multiple instances possible
3. **Respect User Space** - Read-only unless explicitly creating FOR user
4. **Check Before Modify** - Verify task ownership
5. **Namespace Time Entries** - Include 'claude' and 'instance:{id}' tags
6. **Clean Up** - Archive completed work periodically
7. **Communicate** - Tell user about multi-instance scenarios
8. **Be Granular** - Break complex work into trackable pieces
9. **Track Actual Time** - Always update `actual:` UDA
10. **Learn from Data** - Use historical data to improve estimates

## Anti-Patterns to Avoid

❌ Creating tasks without `+claude-work` tag (unless for user)
❌ Modifying user's tasks without permission
❌ Using generic project names that conflict with user
❌ Forgetting instance ID in multi-instance scenarios
❌ Not checking for other active instances
❌ Tracking time without 'claude' tag
❌ Letting Claude tasks pollute user's workflow
❌ Not distinguishing between instances in time tracking

## Quick Reference for New Instances

```bash
# 1. At startup, source helpers and identify
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh
CLAUDE_INSTANCE_ID="claude-$(date +%H%M%S)"

# 2. Check for other instances
task +ACTIVE +claude-work project.startswith:claude.instance

# 3. Create tasks with proper namespacing
task add "User request: X" \
    project:claude.instance.$CLAUDE_INSTANCE_ID \
    +claude-work \
    +instance:$CLAUDE_INSTANCE_ID

# 4. Track time with instance tag
timew start claude instance:$CLAUDE_INSTANCE_ID conversation "X"

# 5. Report only your work
task +instance:$CLAUDE_INSTANCE_ID

# 6. Check user's tasks (read-only)
task -claude-work status:pending
```

## What New Instances Know

When a fresh Claude instance starts:
- **Can see**: Skill exists in available skills list
- **Can see**: Short description of skill
- **CANNOT see**: Full skill content automatically
- **Must do**: Either invoke skill or read file to get full guidance

Therefore, the skill should be designed to:
1. Have clear, actionable description
2. Be easily invokable
3. Provide immediate context when invoked
4. Include startup protocol in first section

## Success Metrics

Track how well this skill is being used:

1. **Task Coverage** - Are significant user requests tracked?
2. **Instance Isolation** - Are instances properly namespaced?
3. **User Respect** - Are user's tasks untouched?
4. **Time Accuracy** - Do actuals match estimates over time?
5. **Context Richness** - Are tasks well-tagged and organized?
6. **User Value** - Do summaries provide useful insights?
7. **Consistency** - Is tracking happening reliably?

---

## Activation

This skill should be active during every conversation where task tracking is appropriate. Use it to:
- Model the work we're doing together
- Track time and effort accurately
- Provide insights into productivity
- Respect user's personal task management
- Coordinate across multiple instances when needed
- Improve planning through historical data
- Give users visibility into progress WITHOUT polluting their workspace

**Remember**: We share the task database with the user. Keep Claude work clearly separated and identifiable!
