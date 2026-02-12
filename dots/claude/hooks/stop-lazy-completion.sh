#!/usr/bin/env bash
# Stop hook: Block if lazy-completion lock is armed

set -euo pipefail

# Debug log
exec 2>/tmp/stop-hook-debug.log
echo "=== Stop hook called at $(date) ===" >&2
echo "PWD: $PWD" >&2
echo "CLAUDE vars: $(env | grep -i claude || echo 'none')" >&2

# Try to find the lock file
LOCK_FILE=""
for candidate in \
  ".claude/completion-lock.md" \
  "${PWD}/.claude/completion-lock.md"; do
  echo "Checking: $candidate" >&2
  if [[ -f $candidate ]]; then
    LOCK_FILE="$candidate"
    echo "Found: $LOCK_FILE" >&2
    break
  fi
done

# If lock file doesn't exist, allow stop
if [[ -z $LOCK_FILE ]]; then
  echo "No lock file found, allowing stop" >&2
  exit 0
fi

# Check if enabled: true in YAML frontmatter (first 10 lines)
ENABLED=$(head -10 "$LOCK_FILE" | grep -E '^enabled:\s*true' || true)
echo "Enabled check result: '$ENABLED'" >&2

if [[ -n $ENABLED ]]; then
  echo "Lock is armed, blocking!" >&2
  MESSAGE=$(awk '/^---$/{if(++c==2){p=1;next}} p' "$LOCK_FILE")

  cat <<EOF
{
  "decision": "block",
  "reason": "**[lazy-completion]** Work incomplete - disarm the lock first"
}
EOF
  exit 0
fi

echo "Lock not armed, allowing stop" >&2
exit 0
