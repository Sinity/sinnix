#!/usr/bin/env bash
# PreToolUse hook for Bash commands
# Blocks dangerous patterns and enforces declarative config

set -euo pipefail

CMD=$(cat | jq -r '.tool_input.command // ""')

emit_deny() {
  local reason="$1"
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
}

# Block imperative package installs
if echo "$CMD" | grep -qE '(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)'; then
  emit_deny "Use declarative config instead of imperative install"
  exit 0
fi

# Block force push
if echo "$CMD" | grep -qE 'git\s+push\s+(-f|--force)|git\s+push\s+.*--force'; then
  emit_deny "Force push blocked - remove flag if intended"
  exit 0
fi

exit 0
