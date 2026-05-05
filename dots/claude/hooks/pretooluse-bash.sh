#!/usr/bin/env bash
# PreToolUse hook for Bash commands.
#
# Blocks dangerous patterns only. Build/test/resource placement is provided by
# project dev environments, not by this hook.

set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

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

# --- Denials -----------------------------------------------------------------

# Block imperative package installs.
# Only at command start or after a command separator — not inside heredocs or strings.
if echo "$CMD" | grep -qE '(^|[;&|]\s*)(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)'; then
  emit_deny "Use declarative config instead of imperative install"
  exit 0
fi

# Block bare force-push (-f, --force) but allow safer variants
# (--force-with-lease, --force-if-includes).
if echo "$CMD" | grep -qE 'git\s+push\s+.*(-f(\s|$)|--force(\s|$))'; then
  emit_deny "Bare force-push blocked — use --force-with-lease or --force-if-includes"
  exit 0
fi

exit 0
