#!/usr/bin/env bash
# Stop hook: Block if lazy-completion lock is armed

set -euo pipefail

emit_stop_block() {
  local reason="$1"
  jq -n --arg reason "$reason" '{ decision: "block", reason: $reason }'
}

LOCK_FILE=""
for candidate in ".claude/completion-lock.md" "${PWD}/.claude/completion-lock.md"; do
  if [[ -f $candidate ]]; then
    LOCK_FILE="$candidate"
    break
  fi
done

# If lock file doesn't exist, allow stop
if [[ -z $LOCK_FILE ]]; then
  exit 0
fi

# Check if enabled: true in YAML frontmatter (first 10 lines)
ENABLED=$(head -10 "$LOCK_FILE" | grep -E '^enabled:\s*true' || true)

if [[ -n $ENABLED ]]; then
  emit_stop_block "**[lazy-completion]** Work incomplete - disarm the lock first"
  exit 0
fi

exit 0
