#!/usr/bin/env bash
# Watch one PR to terminal state and append a typed terminal event.  The
# sinnixd campaign reactor owns bead closure and board persistence.  Capture
# the decision-time receipt before waiting so a later mutable file is never
# consulted by the reaction.
# Usage: merge_close.sh <repo> <pr> [<bead-id> <reason-file>]
set -eu
REPO=$1
PR=$2
BEAD=${3:-}
REASON_FILE=${4:-}
SPOOL=/realm/state/agentctl/events.jsonl
DECIDED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
REASON=
if [ -n "$BEAD" ] && [ -f "$REASON_FILE" ]; then
  REASON=$(<"$REASON_FILE")
fi
for _ in $(seq 1 240); do
  state=$(gh pr view "$PR" -R "$REPO" --json state --jq .state 2>/dev/null) || state=""
  case "$state" in
  MERGED | CLOSED) break ;;
  OPEN | "") sleep 30 ;;
  esac
done

if [ "$state" != "MERGED" ] && [ "$state" != "CLOSED" ]; then state=TIMEOUT; fi
python3 - "$SPOOL" "$REPO" "$PR" "$state" "$BEAD" "$REASON" "$DECIDED_AT" <<'PYEOF'
import hashlib
import json
import pathlib
import sys

spool, repo, pr, state, bead, reason, decided_at = sys.argv[1:]
receipt = None
if bead and reason:
    receipt_payload = {"bead_id": bead, "reason": reason, "decided_at": decided_at}
    receipt_payload["receipt_id"] = hashlib.sha256(
        json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = receipt_payload
event = {
    "schema_version": 1,
    "kind": "merge_close",
    "repo": repo,
    "pr": pr,
    "state": state,
    "decision_receipt": receipt,
}
with pathlib.Path(spool).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()
    import os
    os.fsync(handle.fileno())
PYEOF
