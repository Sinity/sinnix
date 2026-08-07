#!/usr/bin/env bash
# PreToolUse hook for Bash commands.
#
# Blocks dangerous patterns only. Build/test/resource placement is provided by
# project dev environments, not by this hook.

set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

bd_replace_reason=""
bd_replace_script=$(cat <<'PY'
import json
import os
import shlex
import sys

command = os.environ.get("SINNIX_HOOK_COMMAND", "")
try:
    tokens = list(shlex.shlex(command, posix=True, punctuation_chars=";&|"))
except ValueError:
    sys.exit(0)

separators = {";", "&", "|", "&&", "||"}
command_start = True
replace_flags = {"--notes", "--design", "--description", "-d"}

for index, token in enumerate(tokens):
    if token in separators:
        command_start = True
        continue
    if command_start and token == "bd" and index + 1 < len(tokens) and tokens[index + 1] == "update":
        end = index + 2
        while end < len(tokens) and tokens[end] not in separators:
            end += 1
        for option in tokens[index + 2 : end]:
            if option in replace_flags or any(option.startswith(flag + "=") for flag in replace_flags):
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "bd update replace-writes blocked: use --append-notes for note history, "
                            "--design-file or --body-file for file-backed updates, or read-modify-write "
                            "when replacing a field is intentional."
                        ),
                    }
                }))
                sys.exit(0)
        sys.exit(0)
    command_start = False
PY
)
bd_replace_reason="$(SINNIX_HOOK_COMMAND="$CMD" python3 -c "$bd_replace_script")"
if [[ -n "$bd_replace_reason" ]]; then
  printf '%s\n' "$bd_replace_reason"
  exit 0
fi

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
