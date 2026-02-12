# Task Tracking Quick Start for Claude

**NOTE**: Core protocol is in `/realm/project/sinnix/CLAUDE.md` (always in context).
This is a quick reference for common commands.

## Immediate Actions

When you see a **user request**, immediately run:

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh && \
claude_track_request "Description of request" "estimated-time" "priority"
```

When you're **doing significant work** (>2 min), track it:

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh && \
claude_track_coding "What you're coding"
# OR
claude_track_docs "What you're documenting"
# OR
claude_research "What you're researching"
```

When you **discover something** during work:

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh && \
claude_annotate "Your finding or note"
```

When you **complete work**:

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh && \
claude_complete_task <task-id> "actual-time"
```

When user asks **"what have we done?"**:

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh && \
claude_session_summary :day
```

## Pattern Matching

| User Says                  | You Do                                                  |
| -------------------------- | ------------------------------------------------------- |
| "Help me X"                | `claude_track_request "X"`                              |
| "Debug this"               | `claude_track_request "Debug: issue" && tag +debugging` |
| "Research Y"               | `claude_research "Y"`                                   |
| "Write code for Z"         | `claude_track_coding "Z"`                               |
| "Document W"               | `claude_track_docs "W"`                                 |
| "What did we do?"          | `claude_session_summary`                                |
| "What are you working on?" | `claude_status`                                         |

## Decision Tree

```
User makes request?
  YES → claude_track_request "request"
  NO  → Continue

Starting work that will take >2 min?
  YES → Start time tracking (part of track_request or start_task)
  NO  → Skip

Discovered something interesting?
  YES → claude_annotate "finding"
  NO  → Continue

Completed task?
  YES → claude_complete_task <id> "actual-time"
  NO  → Continue

User asks for status?
  YES → claude_status or claude_session_summary
  NO  → Continue
```

## Common Scenarios

### Scenario: User asks you to fix a bug

```bash
# 1. Track it
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh
claude_track_request "Fix: bug description" "45min" "H"

# 2. Work on it (tracking is already started)
# ... investigate, fix, test ...

# 3. Add findings
claude_annotate "Root cause: X"
claude_annotate "Fixed by: Y"

# 4. Complete
claude_complete_task 1 "50min"

# 5. Tell user: "Fixed the bug in 50min"
```

### Scenario: User asks you to build a feature

```bash
# 1. Track main task
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh
claude_track_request "Implement feature X" "2h" "H"

# 2. Create subtasks
task add "Design component" project:conversation depends:1 estimate:30min
task add "Write code" project:conversation depends:1 estimate:1h
task add "Test" project:conversation depends:1 estimate:30min

# 3. Work through subtasks
claude_start_task 2 "design coding"
# ... work ...
claude_complete_task 2 "35min"

claude_start_task 3 "coding"
# ... work ...
claude_complete_task 3 "55min"

# etc.
```

### Scenario: User asks for summary

```bash
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh
claude_session_summary :day

# Then tell user in plain English:
# "Today we completed X tasks:
#  - Task 1 (30min)
#  - Task 2 (45min)
# Total time: 1h 15min on coding and testing."
```

## Remember

- ✓ Track ALL user requests as tasks
- ✓ Time ALL significant work (>2 min)
- ✓ Annotate findings and discoveries
- ✓ Complete tasks with actual times
- ✓ Provide summaries when natural or asked
- ✗ Don't track trivial operations (<2 min)
- ✗ Don't forget to stop tracking when done
- ✗ Don't let user wonder what you're doing - share status!

## Muscle Memory Commands

```bash
# Load helpers (do this once at start)
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh

# Track user request (most common)
claude_track_request "what user wants" "30min" "H"

# Add note to current work
claude_annotate "what I found"

# Check what I'm doing
claude_status

# Complete current work
claude_complete_task <id> "actual-time"

# Show summary
claude_session_summary
```

## Integration Notes

- Helpers are in: `/realm/project/sinnix/dots/taskwarrior/claude-helpers.sh`
- Full skill in: `/realm/project/sinnix/.claude/skills/task-tracking.md`
- Documentation: `/realm/project/sinnix/dots/README-claude-task-tracking.md`

Start using NOW! Track the current conversation as practice.
