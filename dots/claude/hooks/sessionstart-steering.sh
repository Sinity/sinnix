#!/usr/bin/env bash
# SessionStart hook: print the personal steering state into every agent
# session. The operator lives in agent sessions, so this is the ambient
# surface that needs no reminder and no initiative to be seen.
# Exits silently when the steering workspace is absent or bd unavailable.
set -euo pipefail

STEER_BEADS="/realm/project/steering/.beads"
[ -d "$STEER_BEADS" ] || exit 0
command -v bd >/dev/null 2>&1 || exit 0

export BEADS_DIR="$STEER_BEADS"

ready=$(bd ready 2>/dev/null | head -20) || exit 0
[ -n "$ready" ] || exit 0

echo "# Personal Steering — the operator's own intentions, held outside him"
echo "# (what this is: docs/steering.md in sinnix; workspace: /realm/project/steering, bd via BEADS_DIR)"
echo "Open intentions (agent: surface these when relevant; the"
echo "operator steers, you hold state — never nag, always know):"
echo "$ready"
in_prog=$(bd list --status=in_progress 2>/dev/null | head -6) || true
[ -n "$in_prog" ] && {
  echo "In progress:"
  echo "$in_prog"
}
exit 0
