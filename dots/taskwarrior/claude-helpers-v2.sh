#!/usr/bin/env bash
# Claude-specific helper functions for task and time tracking (v2 - Instance Aware)
# These helpers make it easy for Claude to track work during conversations
# while respecting multi-instance scenarios and user's task space

# Initialize instance ID if not already set
if [ -z "$CLAUDE_INSTANCE_ID" ]; then
    # Check for other active instances
    ACTIVE_COUNT=$(task +ACTIVE +claude-work project.startswith:claude.instance count 2>/dev/null || echo "0")

    if [ "$ACTIVE_COUNT" -gt 0 ]; then
        # Other instances active, use unique ID
        export CLAUDE_INSTANCE_ID="claude-$(date +%H%M%S)-$$"
        echo "⚠ Other Claude instances active. Using instance ID: $CLAUDE_INSTANCE_ID"
    else
        # No other instances, use simple ID
        export CLAUDE_INSTANCE_ID="claude-session"
    fi
fi

# Check if task belongs to Claude
claude_owns_task() {
    local task_id="$1"
    task "$task_id" export 2>/dev/null | jq -r '.[0].tags[]?' 2>/dev/null | grep -q 'claude-work'
}

# Check if task belongs to this instance
claude_instance_owns_task() {
    local task_id="$1"
    task "$task_id" export 2>/dev/null | jq -r '.[0].tags[]?' 2>/dev/null | grep -q "instance:$CLAUDE_INSTANCE_ID"
}

# Track a user request (instance-aware)
claude_track_request() {
    local desc="$1"
    local estimate="${2:-30min}"
    local priority="${3:-H}"

    task add "User request: $desc" \
        project:claude.instance.$CLAUDE_INSTANCE_ID \
        priority:"$priority" \
        estimate:"$estimate" \
        tags:user-request,claude-work,instance:$CLAUDE_INSTANCE_ID \
        2>&1 | grep -v "^Filter:"

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1 | grep -v "^Filter:"
        timew start claude instance:$CLAUDE_INSTANCE_ID conversation user-request "$desc" 2>&1 | grep -v "^Filter:"
        echo "✓ Tracking request as task $task_id (instance: $CLAUDE_INSTANCE_ID)"
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

    task add "$desc" \
        project:claude.instance.$CLAUDE_INSTANCE_ID \
        estimate:"$estimate" \
        ${parent_id:+depends:$parent_id} \
        tags:claude-work,instance:$CLAUDE_INSTANCE_ID \
        2>&1 | grep -v "^Filter:"

    local task_id=$(task +LATEST ids 2>/dev/null)
    echo "✓ Created subtask $task_id"
}

# Start working on a task
claude_start_task() {
    local task_id="$1"
    local tags="${2:-conversation}"

    # Check ownership
    if ! claude_instance_owns_task "$task_id"; then
        echo "⚠ Warning: Task $task_id doesn't belong to this instance"
        if ! claude_owns_task "$task_id"; then
            echo "✗ Error: Task $task_id is not a Claude task"
            return 1
        fi
    fi

    # Get task details
    local desc=$(task "$task_id" export 2>/dev/null | jq -r '.[0].description // empty')
    local project=$(task "$task_id" export 2>/dev/null | jq -r '.[0].project // "claude.instance.'$CLAUDE_INSTANCE_ID'"')

    if [ -z "$desc" ]; then
        echo "✗ Task $task_id not found"
        return 1
    fi

    task "$task_id" start 2>&1 | grep -v "^Filter:"
    timew start claude instance:$CLAUDE_INSTANCE_ID "$project" $tags "$desc" 2>&1 | grep -v "^Filter:"
    echo "✓ Started task $task_id: $desc"
}

# Complete a task
claude_complete_task() {
    local task_id="$1"
    local actual="${2:-}"

    # Check ownership
    if ! claude_instance_owns_task "$task_id"; then
        echo "⚠ Warning: Task $task_id doesn't belong to this instance"
        if ! claude_owns_task "$task_id"; then
            echo "✗ Error: Task $task_id is not a Claude task"
            return 1
        fi
    fi

    if [ -n "$actual" ]; then
        task "$task_id" modify actual:"$actual" 2>&1 | grep -v "^Filter:"
    fi

    task "$task_id" done 2>&1 | grep -v "^Filter:"
    timew stop 2>&1 | grep -v "^Filter:"
    echo "✓ Completed task $task_id"
}

# Add a follow-up item (shared project)
claude_followup() {
    local desc="$1"
    local wait="${2:-later}"

    task add "Follow-up: $desc" \
        project:claude.shared \
        wait:"$wait" \
        tags:follow-up,claude-work \
        2>&1 | grep -v "^Filter:"
    echo "✓ Follow-up noted: $desc"
}

# Track research/investigation
claude_research() {
    local topic="$1"
    local estimate="${2:-30min}"

    task add "Research: $topic" \
        project:claude.instance.$CLAUDE_INSTANCE_ID \
        estimate:"$estimate" \
        tags:research,claude-work,instance:$CLAUDE_INSTANCE_ID \
        2>&1 | grep -v "^Filter:"

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1 | grep -v "^Filter:"
        timew start claude instance:$CLAUDE_INSTANCE_ID research conversation "$topic" 2>&1 | grep -v "^Filter:"
        echo "✓ Researching: $topic (task $task_id)"
    fi
}

# Annotate current task
claude_annotate() {
    local finding="$1"

    # Get active task for this instance
    local task_id=$(task +ACTIVE +instance:$CLAUDE_INSTANCE_ID ids 2>/dev/null | head -1)

    if [ -n "$task_id" ]; then
        task "$task_id" annotate "$finding" 2>&1 | grep -v "^Filter:"
        echo "✓ Added note to task $task_id"
    else
        echo "✗ No active task for this instance to annotate"
        return 1
    fi
}

# Show current status (instance-aware)
claude_status() {
    echo "=== Current Work (Instance: $CLAUDE_INSTANCE_ID) ==="

    # Active tasks for this instance
    local active=$(task +ACTIVE +instance:$CLAUDE_INSTANCE_ID export 2>/dev/null | jq -r 'length')
    if [ "$active" -gt 0 ]; then
        echo ""
        echo "My Active Tasks:"
        task +ACTIVE +instance:$CLAUDE_INSTANCE_ID 2>&1 | grep -v "^Filter:"
    else
        echo ""
        echo "No active tasks for this instance"
    fi

    # Current time tracking
    echo ""
    echo "Time Tracking:"
    timew 2>&1 || echo "Not currently tracking time"

    # Check for other instances
    local other_active=$(task +ACTIVE +claude-work project.startswith:claude.instance -instance:$CLAUDE_INSTANCE_ID count 2>/dev/null || echo "0")
    if [ "$other_active" -gt 0 ]; then
        echo ""
        echo "⚠ Other Claude Instances:"
        task +ACTIVE +claude-work project.startswith:claude.instance -instance:$CLAUDE_INSTANCE_ID 2>&1 | grep -v "^Filter:"
    fi

    # Today's progress
    echo ""
    echo "Today's Completed (This Instance):"
    task end.after:today status:completed +instance:$CLAUDE_INSTANCE_ID count 2>&1 | grep -E "^[0-9]+" || echo "0 tasks"
}

# Provide session summary (instance-scoped)
claude_session_summary() {
    local range="${1:-:day}"

    echo "=== Session Summary (Instance: $CLAUDE_INSTANCE_ID) ==="
    echo ""

    # Completed tasks for this instance
    echo "My Completed Tasks:"
    if [ "$range" = ":day" ]; then
        task end.after:today status:completed +instance:$CLAUDE_INSTANCE_ID 2>&1 | grep -v "^Filter:"
    else
        task end.after:today-7days status:completed +instance:$CLAUDE_INSTANCE_ID 2>&1 | grep -v "^Filter:"
    fi

    echo ""
    echo "My Time Breakdown:"
    timew summary "$range" instance:$CLAUDE_INSTANCE_ID :tags 2>&1

    # Still pending for this instance
    echo ""
    echo "Still Pending (This Instance):"
    task status:pending +instance:$CLAUDE_INSTANCE_ID 2>&1 | grep -v "^Filter:"
}

# Show ALL Claude work (all instances)
claude_all_work() {
    echo "=== All Claude Work (All Instances) ==="
    echo ""

    echo "All Active Claude Tasks:"
    task +ACTIVE +claude-work 2>&1 | grep -v "^Filter:"

    echo ""
    echo "Completed Today (All Instances):"
    task end.after:today status:completed +claude-work 2>&1 | grep -v "^Filter:"

    echo ""
    echo "Time Breakdown (All Instances):"
    timew summary :day claude :tags 2>&1
}

# Show user's tasks (read-only)
claude_show_user_tasks() {
    local filter="${1:-status:pending}"

    echo "=== User's Tasks (Read-Only) ==="
    task -claude-work $filter 2>&1 | grep -v "^Filter:"
}

# Create task FOR user (no claude-work tag)
claude_add_for_user() {
    local desc="$1"
    local project="${2:-personal}"
    local priority="${3:-M}"

    task add "$desc" \
        project:"$project" \
        priority:"$priority" \
        2>&1 | grep -v "^Filter:"

    echo "✓ Added to user's tasks: $desc"
}

# Quick stop tracking
claude_stop() {
    local task_id="${1:-}"

    if [ -n "$task_id" ]; then
        if claude_instance_owns_task "$task_id"; then
            task "$task_id" stop 2>&1 | grep -v "^Filter:"
        fi
    fi

    timew stop 2>&1 | grep -v "^Filter:"
    echo "✓ Stopped tracking"
}

# Context switch
claude_switch() {
    local new_context="$1"
    local desc="$2"

    # Stop current
    timew stop 2>&1 | grep -v "^Filter:" || true

    # Start new
    if [ -n "$desc" ]; then
        timew start claude instance:$CLAUDE_INSTANCE_ID "$new_context" "$desc" 2>&1 | grep -v "^Filter:"
        echo "✓ Switched to: $new_context - $desc"
    else
        echo "✓ Stopped tracking"
    fi
}

# Show what needs review
claude_review_needed() {
    echo "=== Tasks Needing Review (Claude Work) ==="
    task review +claude-work 2>&1 | grep -v "^Filter:"
}

# Quick task for code work
claude_track_coding() {
    local desc="$1"
    local estimate="${2:-45min}"

    task add "$desc" \
        project:claude.instance.$CLAUDE_INSTANCE_ID \
        estimate:"$estimate" \
        energy:high \
        tags:coding,claude-work,instance:$CLAUDE_INSTANCE_ID \
        2>&1 | grep -v "^Filter:"

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1 | grep -v "^Filter:"
        timew start claude instance:$CLAUDE_INSTANCE_ID coding conversation "$desc" 2>&1 | grep -v "^Filter:"
        echo "✓ Coding: $desc (task $task_id)"
    fi
}

# Track documentation work
claude_track_docs() {
    local desc="$1"
    local estimate="${2:-20min}"

    task add "$desc" \
        project:claude.instance.$CLAUDE_INSTANCE_ID \
        estimate:"$estimate" \
        energy:medium \
        tags:documentation,claude-work,instance:$CLAUDE_INSTANCE_ID \
        2>&1 | grep -v "^Filter:"

    local task_id=$(task +LATEST ids 2>/dev/null)

    if [ -n "$task_id" ]; then
        task "$task_id" start 2>&1 | grep -v "^Filter:"
        timew start claude instance:$CLAUDE_INSTANCE_ID documentation conversation "$desc" 2>&1 | grep -v "^Filter:"
        echo "✓ Documenting: $desc (task $task_id)"
    fi
}

# Get latest task ID for this instance
claude_latest_id() {
    task +LATEST +instance:$CLAUDE_INSTANCE_ID ids 2>/dev/null
}

# Check instance information
claude_instance_info() {
    echo "Instance ID: $CLAUDE_INSTANCE_ID"
    echo "Active tasks: $(task +ACTIVE +instance:$CLAUDE_INSTANCE_ID count 2>/dev/null || echo "0")"
    echo "Other instances: $(task +ACTIVE +claude-work project.startswith:claude.instance -instance:$CLAUDE_INSTANCE_ID count 2>/dev/null || echo "0")"
}

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
alias cinfo='claude_instance_info'

echo "Claude task tracking helpers v2 loaded ✓ (Instance: $CLAUDE_INSTANCE_ID)"
