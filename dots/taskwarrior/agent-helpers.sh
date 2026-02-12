#!/usr/bin/env bash
# Agent-agnostic helper functions for task and time tracking.

if [ -z "${AGENT_NAME:-}" ]; then
  echo "AGENT_NAME is required (e.g. codex, claude)."
  return 1
fi

if [ -z "${AGENT_SESSION_ID:-}" ]; then
  export AGENT_SESSION_ID="${AGENT_NAME}-$(date +%H%M%S)-$$"
fi

export AGENT_NAME
export AGENT_SESSION_ID

AGENT_NAME_TAG="agent_${AGENT_NAME}"
AGENT_SESSION_TAG="session_${AGENT_SESSION_ID}"
AGENT_PROJECT="agent.${AGENT_NAME}.${AGENT_SESSION_ID}"
AGENT_PROJECT_PREFIX="agent.${AGENT_NAME}."
AGENT_SHARED_PROJECT="agent.shared"

agent_project() {
  echo "$AGENT_PROJECT"
}

agent_owns_task() {
  local task_id="$1"
  local project
  project=$(task "$task_id" export 2>/dev/null | jq -r '.[0].project // ""' 2>/dev/null)
  [[ $project == agent.* ]]
}

agent_session_owns_task() {
  local task_id="$1"
  local project
  project=$(task "$task_id" export 2>/dev/null | jq -r '.[0].project // ""' 2>/dev/null)
  [[ $project == "$AGENT_PROJECT" ]]
}

agent_track_request() {
  local desc="$1"
  local estimate="${2:-30min}"
  local priority="${3:-H}"

  task add "User request: $desc" \
    project:"$AGENT_PROJECT" \
    priority:"$priority" \
    estimate:"$estimate" \
    tags:agent,user_request \
    2>&1 | grep -v "^Filter:"

  local task_id
  task_id=$(task +LATEST ids 2>/dev/null)

  if [ -n "$task_id" ]; then
    task "$task_id" start 2>&1 | grep -v "^Filter:"
    timew start agent "$AGENT_NAME_TAG" "$AGENT_SESSION_TAG" conversation user_request 2>&1 | grep -v "^Filter:"
    echo "✓ Tracking request as task $task_id (${AGENT_NAME}/${AGENT_SESSION_ID})"
    return 0
  fi

  echo "✗ Failed to create task"
  return 1
}

agent_start_task() {
  local task_id="$1"
  shift || true
  local tags=("$@")
  if [ "${#tags[@]}" -eq 0 ]; then
    tags=(conversation)
  fi

  if ! agent_session_owns_task "$task_id"; then
    echo "⚠ Task $task_id is not in this session"
    if ! agent_owns_task "$task_id"; then
      echo "✗ Task $task_id is not an agent task"
      return 1
    fi
  fi

  local desc
  desc=$(task "$task_id" export 2>/dev/null | jq -r '.[0].description // empty')
  if [ -z "$desc" ]; then
    echo "✗ Task $task_id not found"
    return 1
  fi

  task "$task_id" start 2>&1 | grep -v "^Filter:"
  timew start agent "$AGENT_NAME_TAG" "$AGENT_SESSION_TAG" "${tags[@]}" 2>&1 | grep -v "^Filter:"
  echo "✓ Started task $task_id: $desc"
}

agent_complete_task() {
  local task_id="$1"
  local actual="${2:-}"

  if ! agent_session_owns_task "$task_id"; then
    echo "⚠ Task $task_id is not in this session"
    if ! agent_owns_task "$task_id"; then
      echo "✗ Task $task_id is not an agent task"
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

agent_followup() {
  local desc="$1"
  local wait="${2:-later}"

  task add "Follow-up: $desc" \
    project:"$AGENT_SHARED_PROJECT" \
    wait:"$wait" \
    tags:agent,follow_up \
    2>&1 | grep -v "^Filter:"
  echo "✓ Follow-up noted: $desc"
}

agent_annotate() {
  local finding="$1"
  local task_id
  task_id=$(task +ACTIVE project:"$AGENT_PROJECT" ids 2>/dev/null | head -1)

  if [ -n "$task_id" ]; then
    task "$task_id" annotate "$finding" 2>&1 | grep -v "^Filter:"
    echo "✓ Added note to task $task_id"
  else
    echo "✗ No active task for this session"
    return 1
  fi
}

agent_status() {
  echo "=== Work (${AGENT_NAME}/${AGENT_SESSION_ID}) ==="
  echo ""

  local active
  active=$(task +ACTIVE project:"$AGENT_PROJECT" export 2>/dev/null | jq -r 'length')
  if [ "${active:-0}" -gt 0 ]; then
    task +ACTIVE project:"$AGENT_PROJECT" 2>&1 | grep -v "^Filter:"
  else
    echo "No active tasks for this session"
  fi

  echo ""
  echo "Time Tracking:"
  timew 2>&1 || echo "Not currently tracking time"
}

agent_session_summary() {
  local range="${1:-:day}"

  echo "=== Session Summary (${AGENT_NAME}/${AGENT_SESSION_ID}) ==="
  echo ""
  echo "Completed Tasks:"
  task end.after:today status:completed project:"$AGENT_PROJECT" 2>&1 | grep -v "^Filter:"

  echo ""
  echo "Time Summary:"
  timew summary "$range" "$AGENT_SESSION_TAG" :tags 2>&1
}

agent_show_user_tasks() {
  local filter="${1:-status:pending}"
  echo "=== User Tasks (Read-Only) ==="
  task -agent $filter 2>&1 | grep -v "^Filter:"
}

agent_stop() {
  local task_id="${1:-}"
  if [ -n "$task_id" ] && agent_session_owns_task "$task_id"; then
    task "$task_id" stop 2>&1 | grep -v "^Filter:"
  fi
  timew stop 2>&1 | grep -v "^Filter:"
  echo "✓ Stopped tracking"
}

alias atr='agent_track_request'
alias ast='agent_start_task'
alias adone='agent_complete_task'
alias anote='agent_annotate'
alias astatus='agent_status'
alias asummary='agent_session_summary'
alias astop='agent_stop'

echo "Agent task helpers loaded ✓ (${AGENT_NAME}/${AGENT_SESSION_ID})"
