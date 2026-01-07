#!/usr/bin/env bash
# Shell aliases and functions for Taskwarrior and Timewarrior
# Source this file in your shell configuration (.bashrc, .zshrc, etc.)

# Taskwarrior aliases
alias t='task'
alias ta='task add'
alias tl='task list'
alias tn='task next'
alias to='task overdue'
alias tw='task waiting'
alias ts='task someday'
alias tr='task review'
alias tq='task quickwins'
alias ti='task inbox'
alias tp='task proj'

# Taskwarrior GTD workflow
alias tcapture='task add +inbox'
alias tclarify='task inbox'
alias treview='task review'
alias tnext='task next'

# Taskwarrior context switching
alias tc='task context'
alias tcw='task context work'
alias tch='task context home'
alias tcc='task context coding'
alias tcq='task context quick'
alias tcd='task context deep'
alias tcn='task context none'

# Timewarrior aliases
alias tw='timew'
alias tws='timew summary'
alias twd='timew day'
alias tww='timew week'
alias twm='timew month'
alias twstart='timew start'
alias twstop='timew stop'
alias twcont='timew continue'
alias twcancel='timew cancel'

# Custom Timewarrior reports
function twbalance() {
    local range="${1:-:week}"
    timew export "$range" | python3 ~/.config/timewarrior/extensions/balance.py
}

function twprod() {
    local range="${1:-:week}"
    timew export "$range" | python3 ~/.config/timewarrior/extensions/productivity.py
}

# Combined functions
function twork() {
    # Start working on a specific task and track time
    if [ -z "$1" ]; then
        echo "Usage: twork <task-id>"
        return 1
    fi

    task "$1" start

    # Get task details for timewarrior
    local desc=$(task "$1" export | jq -r '.[0].description')
    local tags=$(task "$1" export | jq -r '.[0].tags[]?' | tr '\n' ' ')
    local project=$(task "$1" export | jq -r '.[0].project // empty')

    # Start timewarrior tracking
    if [ -n "$project" ] && [ -n "$tags" ]; then
        timew start "$project" $tags "$desc"
    elif [ -n "$project" ]; then
        timew start "$project" "$desc"
    elif [ -n "$tags" ]; then
        timew start $tags "$desc"
    else
        timew start "$desc"
    fi
}

function tstop() {
    # Stop current task in both taskwarrior and timewarrior
    if [ -z "$1" ]; then
        # Find currently active task
        local active_id=$(task +ACTIVE ids)
        if [ -n "$active_id" ]; then
            task "$active_id" stop
            timew stop
        else
            echo "No active task found"
            return 1
        fi
    else
        task "$1" stop
        timew stop
    fi
}

function tdone() {
    # Complete a task and stop timewarrior
    if [ -z "$1" ]; then
        echo "Usage: tdone <task-id>"
        return 1
    fi

    task "$1" done
    timew stop
}

# Quick task entry with immediate start
function tquick() {
    if [ -z "$1" ]; then
        echo "Usage: tquick <description> [+tags] [project:name]"
        return 1
    fi

    # Add and start the task
    local task_id=$(task add "$@" | grep -oP 'Created task \K\d+')
    if [ -n "$task_id" ]; then
        twork "$task_id"
    fi
}

# Review workflow
function treviewday() {
    echo "=== Today's Completed Tasks ==="
    task dailystatus

    echo ""
    echo "=== Current Active Tasks ==="
    task +ACTIVE

    echo ""
    echo "=== Time Tracking Summary ==="
    timew summary :day

    echo ""
    echo "=== Work-Life Balance ==="
    twbalance :day
}

function treviewweek() {
    echo "=== This Week's Summary ==="
    task weekly

    echo ""
    echo "=== Time Tracking Summary ==="
    timew summary :week

    echo ""
    echo "=== Work-Life Balance ==="
    twbalance :week

    echo ""
    echo "=== Productivity Analysis ==="
    twprod :week
}

# Pomodoro-style work session
function tpomodoro() {
    local duration="${1:-25}"
    local task_id="$2"

    if [ -z "$task_id" ]; then
        echo "Usage: tpomodoro [duration-in-minutes] <task-id>"
        return 1
    fi

    echo "Starting ${duration}-minute work session on task $task_id"
    twork "$task_id"

    sleep "${duration}m"

    echo "Work session complete!"
    tstop "$task_id"
}

# Export functions
export -f twbalance twprod twork tstop tdone tquick treviewday treviewweek tpomodoro
