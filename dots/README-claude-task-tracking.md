># Claude Task Tracking System

This document describes how Claude uses Taskwarrior and Timewarrior to track work, model tasks, and provide insights during conversations.

## Overview

Claude has been configured with:
1. **Skill**: `/realm/project/sinnix/.claude/skills/task-tracking.md` - Comprehensive guidance on when/how to use task tracking
2. **Helper Scripts**: `/realm/project/sinnix/dots/taskwarrior/claude-helpers.sh` - Shell functions for easy tracking
3. **Integration**: Hooks and automation to make tracking seamless

## How It Works

### During Conversations, Claude Will:

1. **Create Tasks** for:
   - User requests (tagged `+user-request`)
   - Significant work items (>3 tool calls or >5 minutes)
   - Follow-up items discovered during work
   - Research and investigation
   - Bugs and issues found

2. **Track Time** on:
   - All significant work (>2 minutes)
   - Active coding, debugging, research
   - Documentation and planning

3. **Provide Insights** via:
   - Progress updates during work
   - Session summaries at natural break points
   - Time breakdown by activity type
   - Productivity pattern analysis

### Task Organization

**Projects**: Hierarchical organization
- `conversation` - Current conversation work
- `conversation.{topic}` - Specific topics
- `sinnix` - Sinnix project tasks
- `sinnix.{component}` - Specific components

**Tags**: Semantic categorization
- `+user-request` - Direct user requests
- `+follow-up` - Needs follow-up
- `+research` - Investigation work
- `+coding`, `+documentation`, `+testing`, etc.

**UDAs**: Rich metadata
- `estimate:30min` - Estimated effort
- `actual:45min` - Actual time spent
- `energy:high` - Required energy level
- `complexity:moderate` - Complexity assessment
- `impact:high` - Impact level

## Helper Functions Available

```bash
# Source helpers
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh

# Track user request
claude_track_request "Description" "30min" "H"

# Start working on a task
claude_start_task <task-id> "tags"

# Complete a task
claude_complete_task <task-id> "45min"

# Add follow-up
claude_followup "Check this later"

# Track research
claude_research "Topic" "30min"

# Annotate current task
claude_annotate "Finding or note"

# Show current status
claude_status

# Session summary
claude_session_summary :day

# Stop tracking
claude_stop

# Context switch
claude_switch "new-context" "description"

# Track coding work
claude_track_coding "Implement feature X"

# Track documentation
claude_track_docs "Write API docs"
```

## Example Workflow

### User Makes Request

```bash
# Claude creates task and starts tracking
source /realm/project/sinnix/dots/taskwarrior/claude-helpers.sh
claude_track_request "Fix authentication bug" "1h" "H"
# Output: ✓ Tracking request as task 42

# Claude works and adds findings
claude_annotate "Root cause: JWT validation timing issue"
claude_annotate "Fix: Update token refresh logic"

# Claude completes work
claude_complete_task 42 "55min"
# Output: ✓ Completed task 42
```

### Complex Multi-Step Work

```bash
# Main task
claude_track_request "Implement dark mode" "2h" "H"
# Gets task ID 43

# Subtasks
task add "Design toggle component" project:conversation depends:43 estimate:30min
task add "Add state management" project:conversation depends:43 estimate:30min
task add "Update CSS" project:conversation depends:43 estimate:45min

# Work through each
claude_start_task 44 "coding design"
# ... work ...
claude_complete_task 44 "35min"

# Parent completes when all subtasks done
```

### Session Summary

```bash
# At end of session or when user asks
claude_session_summary :day

# Output includes:
# - Completed tasks
# - Time breakdown by tags
# - Pending work
```

## What You'll See

### Progress Updates

Claude will occasionally share:
- "Created task for: {description}"
- "Currently working on: {task}"
- "Completed {n} tasks so far"
- "Spent ~{time} on {activity}"

### Session Summaries

When appropriate, Claude will provide:
```
Session Summary:
- Completed 4 tasks across 2 projects
- Time: 1h 45min (60% coding, 25% documentation, 15% research)
- Most productive: Hour 2-3
- Still pending: 2 tasks
```

### Time Insights

Using custom extensions:
- Work-life balance (if applicable)
- Productivity patterns by time of day
- Activity distribution

## Viewing Claude's Work

You can always check what Claude has been working on:

```bash
# Currently active
task +ACTIVE

# Completed today
task end.after:today status:completed

# Pending conversation tasks
task status:pending project:conversation

# Time tracking summary
timew summary :day :ids

# Detailed task view
task 1 info

# All conversation work
task project:conversation
```

## Benefits

1. **Transparency** - See exactly what Claude is working on
2. **Accountability** - Track time spent on different activities
3. **Learning** - Improve estimates over time based on actuals
4. **Planning** - Better understand complexity and effort
5. **Insights** - Identify patterns and optimize workflow
6. **History** - Complete record of work done together

## Configuration

The skill is configured to be:
- **Proactive** - Claude uses it without being asked
- **Lightweight** - Minimal overhead, focuses on significant work
- **Informative** - Provides useful insights and summaries
- **Consistent** - Uses standard patterns and conventions

## Customization

You can adjust Claude's tracking behavior by:

1. **Editing the skill**: `/realm/project/sinnix/.claude/skills/task-tracking.md`
2. **Modifying helpers**: `/realm/project/sinnix/dots/taskwarrior/claude-helpers.sh`
3. **Providing feedback**: "Track more/less detail", "Provide summaries more/less often"

## Integration with Previous Setup

This builds on the advanced Taskwarrior/Timewarrior configuration:
- Uses the same UDAs, contexts, and reports
- Leverages custom themes and extensions
- Follows the same organizational patterns
- Benefits from the same hooks and automation

## Example Session

```
User: "Help me debug the authentication issue"

Claude: "I'll investigate this for you."
[Creates task: "User request: Debug authentication issue"]
[Starts time tracking: research, debugging, conversation]

Claude: "I've found the issue - it's in the JWT validation..."
[Annotates task with findings]

Claude: "I've created a fix and tested it."
[Completes task with actual time: 35min]
[Stops time tracking]

User: "What else did we work on today?"

Claude: "Today we completed 3 tasks:
- Debug authentication issue (35min)
- Update API documentation (20min)
- Configure logging system (15min)
Total: 1h 10min across debugging, documentation, and configuration."
```

## Notes

- **Privacy**: All task data stays local in `~/.task/` and `~/.local/share/timewarrior/`
- **Persistence**: Tasks and time tracking persist across conversations
- **Flexibility**: System adapts to different types of work
- **Non-intrusive**: Tracking happens in background, user only sees summaries when relevant

## Getting Started

The system is active now. Just start a conversation and Claude will:
1. Track your requests as tasks
2. Time significant work
3. Provide progress updates
4. Offer summaries when appropriate

No configuration needed - it's ready to use!

## Quick Reference

```bash
# View Claude's active work
task +ACTIVE project:conversation

# See today's progress
task dailystatus

# Check time tracking
timew

# View session summary
timew summary :day :tags

# See all conversation tasks
task project:conversation

# Get task details
task <id> info

# Force a summary
# (Just ask Claude: "What have we accomplished?")
```

---

This system makes Claude's work transparent, measurable, and continuously improving!
