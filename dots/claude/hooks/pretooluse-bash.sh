#!/usr/bin/env bash
# PreToolUse hook for Bash commands
# Blocks dangerous patterns and enforces declarative config

set -euo pipefail

CMD=$(cat | jq -r '.tool_input.command // ""')

# Block imperative package installs
if echo "$CMD" | grep -qE '(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)'; then
  echo '{"decision":"block","reason":"Use declarative config instead of imperative install"}'
  exit 0
fi

# Block rm -rf
if echo "$CMD" | grep -qE 'rm\s+(-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)\s'; then
  echo '{"decision":"block","reason":"Use trash instead of rm -rf"}'
  exit 0
fi

# Block force push
if echo "$CMD" | grep -qE 'git\s+push\s+(-f|--force)|git\s+push\s+.*--force'; then
  echo '{"decision":"block","reason":"Force push blocked - remove flag if intended"}'
  exit 0
fi

exit 0
