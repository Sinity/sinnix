# Task and Time Tracking Protocol

**ALWAYS ACTIVE**: Use taskwarrior and timewarrior to track work during conversations in this project.

## Critical Rules

1. **Instance Identification**
   ```bash
   # At conversation start, set instance ID
   CLAUDE_INSTANCE_ID="${CLAUDE_INSTANCE_ID:-claude-$(date +%H%M%S)-$$}"
   ```

2. **Separation of Concerns**
   - All Claude tasks must have `+claude-work` tag.
   - All Claude tasks use `project:claude.*` hierarchy.
   - User tasks have no `+claude-work` tag and are read-only unless asked.

3. **Project Namespacing**
   ```
   claude.instance.{id}     <- This instance's work
   claude.shared.{topic}    <- Shared across instances
   {anything-else}          <- User's tasks (read-only)
   ```

4. **Ownership Verification**
   ```bash
   # Before modifying ANY task, verify ownership:
   if task {id} export | jq -r '.[0].tags[]?' | grep -q 'claude-work'; then
       # Safe - Claude's task
   else
       # STOP - User's task, ask permission
   fi
   ```

## When to Track

**Create tasks for:**
- User requests (`+user-request`)
- Multi-step work (>3 tool calls or >5 minutes)
- Research and investigation (`+research`)
- Follow-up items (`+follow-up`)

**Track time on:**
- All significant work (>2 minutes)
- Use tags: `claude`, `instance:{id}`, `{activity}`

## Core Commands

**Using helpers** (recommended):
```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers-v2.sh

# Track user request
claude_track_request "Description" "30min" "H"

# Annotate current work
claude_annotate "Finding or note"

# Complete task
claude_complete_task {id} "actual-time"

# Show status
claude_status

# Session summary
claude_session_summary
```

**Direct usage**:
```bash
# Create task with proper namespacing
task add "User request: {desc}" \
    project:claude.instance.$CLAUDE_INSTANCE_ID \
    priority:H \
    +user-request \
    +claude-work \
    +instance:$CLAUDE_INSTANCE_ID \
    estimate:30min

# Track time
timew start claude instance:$CLAUDE_INSTANCE_ID conversation "{desc}"

# Complete
task {id} modify actual:45min
task {id} done
timew stop
```

## Read-Only User Task Interaction

**CAN do:**
```bash
# Read user's tasks
task -claude-work status:pending

# Report to user
"You have 5 tasks due today in your 'work' project"

# Create task FOR user (if asked)
task add "Buy milk" project:personal  # NO +claude-work tag
```

**CANNOT do:**
- Modify user's tasks without explicit permission
- Delete user's tasks
- Add `+claude-work` to user's tasks
- Track time on user's tasks (unless asked)

## Multi-Instance Coordination

**Check for others at startup:**
```bash
OTHERS=$(task +ACTIVE +claude-work project.startswith:claude.instance count)
if [ "$OTHERS" -gt 0 ]; then
    echo "WARNING: $OTHERS other Claude instance(s) active"
fi
```

**View separation:**
```bash
# My instance only
task +instance:$CLAUDE_INSTANCE_ID

# Other instances
task +ACTIVE +claude-work -instance:$CLAUDE_INSTANCE_ID

# All Claude work
task +claude-work

# User's tasks only
task -claude-work
```

## Proactive Behavior

**MUST track when:**
1. User makes explicit request
2. Starting significant work (>2 min)
3. Discovering issues or findings
4. Creating follow-up items

**Report when:**
- User asks "what have we done?"
- Natural break points in conversation
- Completing major work

**Quick summary format:**
```
"Completed {n} tasks:
- Task A (30min)
- Task B (45min)
Total: 1h 15min on {activities}"
```

## Anti-Patterns (Avoid)

- Creating tasks without `+claude-work`
- Using `project:conversation` (use `project:claude.instance.{id}`)
- Modifying tasks without ownership check
- Forgetting instance ID in multi-instance scenarios
- Tracking time without `claude` tag
- Polluting user's task space

## Quick Reference Card

```bash
# At conversation start
source /realm/project/sinnix/dots/taskwarrior/claude-helpers-v2.sh
# (Sets CLAUDE_INSTANCE_ID automatically)

# User makes request
claude_track_request "What they want" "estimate" "priority"

# During work
claude_annotate "What I discovered"

# Complete work
claude_complete_task {id} "actual-time"

# Status check
claude_status              # My work
task -claude-work          # User's tasks
claude_session_summary     # Summary
```

## File Locations

- Helpers: `/realm/project/sinnix/dots/taskwarrior/claude-helpers-v2.sh`
- Detailed skill: `/realm/project/sinnix/.claude/skills/task-tracking.md`
- Multi-instance FAQ: `/realm/project/sinnix/dots/README-claude-multi-instance-faq.md`
- User guide: `/realm/project/sinnix/dots/README-claude-task-tracking.md`

## Success Criteria

- Every significant user request is tracked
- All Claude tasks have `+claude-work`
- Instance IDs prevent conflicts
- User's tasks remain untouched
- Time tracking provides insights
- Summaries are helpful and accurate
