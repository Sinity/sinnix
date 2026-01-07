#!/usr/bin/env bash
# Claude-specific helper functions for task and time tracking
# These helpers make it easy for Claude to track work during conversations

# Track a user request
claude_track_request() {
    local desc="$1"
    local estimate="${2:-30min}"
    local priority="${3:-H}"

    task add "User request: $desc" \
        project:conversation \
        priority:"$priority" \
        +user-request \
        estimate:"$estimate" \
        2>&1 | tee /tmp/task_add.log

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1
        timew start conversation user-request "$desc" 2>&1
        echo "✓ Tracking request as task $task_id"
        return 0
    else
        echo "✗ Failed to create task"
        return 1
    fi
}

# Track a subtask
claude_track_subtask() {
    local desc="$1"
    local parent_id="$2"
    local estimate="${3:-15min}"

    local cmd="task add \"$desc\" project:conversation estimate:\"$estimate\""

    if [ -n "$parent_id" ]; then
        cmd="$cmd depends:$parent_id"
    fi

    eval "$cmd" 2>&1

    local task_id=$(task +LATEST ids 2>/dev/null)
    echo "✓ Created subtask $task_id"
}

# Start working on a task
claude_start_task() {
    local task_id="$1"
    local tags="${2:-conversation}"

    # Get task details
    local desc=$(task "$task_id" export 2>/dev/null | jq -r '.[0].description // empty')
    local project=$(task "$task_id" export 2>/dev/null | jq -r '.[0].project // "conversation"')

    if [ -z "$desc" ]; then
        echo "✗ Task $task_id not found"
        return 1
    fi

    task "$task_id" start 2>&1
    timew start "$project" $tags "$desc" 2>&1
    echo "✓ Started task $task_id: $desc"
}

# Complete a task
claude_complete_task() {
    local task_id="$1"
    local actual="${2:-}"

    if [ -n "$actual" ]; then
        task "$task_id" modify actual:"$actual" 2>&1
    fi

    task "$task_id" done 2>&1
    timew stop 2>&1
    echo "✓ Completed task $task_id"
}

# Add a follow-up item
claude_followup() {
    local desc="$1"
    local wait="${2:-later}"

    task add "Follow-up: $desc" +follow-up wait:"$wait" 2>&1
    echo "✓ Follow-up noted: $desc"
}

# Track research/investigation
claude_research() {
    local topic="$1"
    local estimate="${2:-30min}"

    task add "Research: $topic" \
        project:conversation \
        +research \
        estimate:"$estimate" \
        2>&1

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1
        timew start research conversation "$topic" 2>&1
        echo "✓ Researching: $topic (task $task_id)"
    fi
}

# Annotate current task
claude_annotate() {
    local finding="$1"

    # Get active task
    local task_id=$(task +ACTIVE ids 2>/dev/null | head -1)

    if [ -n "$task_id" ]; then
        task "$task_id" annotate "$finding" 2>&1
        echo "✓ Added note to task $task_id"
    else
        echo "✗ No active task to annotate"
        return 1
    fi
}

# Show current status (what Claude is working on)
claude_status() {
    echo "=== Current Work ==="

    # Active tasks
    local active=$(task +ACTIVE export 2>/dev/null | jq -r 'length')
    if [ "$active" -gt 0 ]; then
        echo ""
        echo "Active Tasks:"
        task +ACTIVE 2>&1
    fi

    # Current time tracking
    echo ""
    echo "Time Tracking:"
    timew 2>&1 || echo "Not currently tracking time"

    # Today's progress
    echo ""
    echo "Today's Completed:"
    task end.after:today status:completed count 2>&1 | grep -E "^[0-9]+" || echo "0 tasks"
}

# Provide session summary
claude_session_summary() {
    local range="${1:-:day}"

    echo "=== Session Summary ==="
    echo ""

    # Completed tasks
    echo "Completed Tasks:"
    if [ "$range" = ":day" ]; then
        task end.after:today status:completed 2>&1
    else
        task end.after:today-7days status:completed 2>&1
    fi

    echo ""
    echo "Time Breakdown:"
    timew summary "$range" :tags 2>&1

    # Active/pending tasks
    echo ""
    echo "Still Pending:"
    task status:pending project:conversation 2>&1
}

# Quick stop tracking
claude_stop() {
    local task_id="${1:-}"

    if [ -n "$task_id" ]; then
        task "$task_id" stop 2>&1
    fi

    timew stop 2>&1
    echo "✓ Stopped tracking"
}

# Context switch
claude_switch() {
    local new_context="$1"
    local desc="$2"

    # Stop current
    timew stop 2>&1 || true

    # Start new
    if [ -n "$desc" ]; then
        timew start "$new_context" "$desc" 2>&1
        echo "✓ Switched to: $new_context - $desc"
    else
        echo "✓ Stopped tracking"
    fi
}

# Show what needs review
claude_review_needed() {
    echo "=== Tasks Needing Review ==="
    task review 2>&1
}

# Quick task for code work
claude_track_coding() {
    local desc="$1"
    local estimate="${2:-45min}"

    task add "$desc" \
        project:conversation \
        +coding \
        estimate:"$estimate" \
        energy:high \
        2>&1

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1
        timew start coding conversation "$desc" 2>&1
        echo "✓ Coding: $desc (task $task_id)"
    fi
}

# Track documentation work
claude_track_docs() {
    local desc="$1"
    local estimate="${2:-20min}"

    task add "$desc" \
        project:conversation \
        +documentation \
        estimate:"$estimate" \
        energy:medium \
        2>&1

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1
        timew start documentation conversation "$desc" 2>&1
        echo "✓ Documenting: $desc (task $task_id)"
    fi
}

# Get latest task ID
claude_latest_id() {
    task +LATEST ids 2>/dev/null
}

# Export functions
export -f claude_track_request claude_track_subtask claude_start_task
export -f claude_complete_task claude_followup claude_research
export -f claude_annotate claude_status claude_session_summary
export -f claude_stop claude_switch claude_review_needed
export -f claude_track_coding claude_track_docs claude_latest_id

# Aliases for shorter commands
alias ct='claude_track_request'
alias cs='claude_start_task'
alias cd='claude_complete_task'
alias cf='claude_followup'
alias cr='claude_research'
alias ca='claude_annotate'
alias cstat='claude_status'
alias csum='claude_session_summary'
alias cstop='claude_stop'

echo "Claude task tracking helpers loaded ✓"
