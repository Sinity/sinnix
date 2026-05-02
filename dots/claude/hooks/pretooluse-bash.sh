#!/usr/bin/env bash
# PreToolUse hook for Bash commands.
#
# Two responsibilities:
#   1. Block dangerous patterns (imperative installs, bare force-push).
#   2. Rewrap heavy I/O commands (pytest in any invocation form) through
#      sinnix-scope so they enter build.slice.
#
# Slice rewrap uses `hookSpecificOutput.updatedInput` to transparently
# replace `tool_input.command`. The agent sees `systemMessage` explaining
# what was rewrapped; subsequent output is unchanged.

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

emit_rewrite() {
  local new_cmd="$1"
  local note="$2"
  jq -n \
    --arg cmd "$new_cmd" \
    --arg note "$note" \
    '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "allow",
        updatedInput: { command: $cmd }
      },
      systemMessage: $note
    }'
}

# --- Denials -----------------------------------------------------------------

# Block imperative package installs.
if echo "$CMD" | grep -qE '(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)'; then
  emit_deny "Use declarative config instead of imperative install"
  exit 0
fi

# Block bare force-push (-f, --force) but allow safer variants
# (--force-with-lease, --force-if-includes).
if echo "$CMD" | grep -qE 'git\s+push\s+.*(-f(\s|$)|--force(\s|$))'; then
  emit_deny "Bare force-push blocked — use --force-with-lease or --force-if-includes"
  exit 0
fi

# --- Slice rewraps -----------------------------------------------------------

# Already inside build.slice (re-entrant systemd-run, recursive invocation,
# or wrapper script that already self-promoted). Pass through unchanged.
if echo "$CMD" | grep -qE 'systemd-run.*build\.slice|--slice=build\.slice'; then
  exit 0
fi

# Detect any pytest invocation:
#   - bare `pytest`
#   - `python -m pytest`, `python3 -m pytest`, `uv run pytest`, `poetry run pytest`
#   - absolute/venv paths: `.venv/bin/pytest`, `/path/to/pytest`
# Word-boundary anchored to avoid hits in arbitrary substrings.
if echo "$CMD" | grep -qE '(^|[^[:alnum:]_./-])(pytest|python[0-9.]*[[:space:]]+-m[[:space:]]+pytest|(uv|poetry|pdm|hatch|rye)[[:space:]]+run[[:space:]]+pytest|[./][^[:space:]]*/pytest)([[:space:]]|$)'; then
  # Wrap the entire command in a build.slice scope. Use bash -lc so shell
  # features (pipes, redirects, env vars, &&) survive the wrap intact.
  # POSIX single-quote escape: every "'" becomes "'\''", whole payload wrapped
  # in single quotes — bash then sees the original command literally.
  ESCAPED=$(printf '%s' "$CMD" | sed "s/'/'\\\\''/g")
  WRAPPED="sinnix-scope build -- bash -lc '$ESCAPED'"
  emit_rewrite "$WRAPPED" "Rewrapped pytest invocation through sinnix-scope build."
  exit 0
fi

exit 0
