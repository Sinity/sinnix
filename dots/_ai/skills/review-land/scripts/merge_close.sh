#!/usr/bin/env bash
# Watch one PR to terminal state; on MERGED, close the linked bead with the
# receipt written at decision time and update the campaign board. Appends a
# terminal event to the agentctl spool either way.
# Usage: merge_close.sh <repo> <pr> [<bead-id> <reason-file>]
set -u
REPO=$1; PR=$2; BEAD=${3:-}; REASON_FILE=${4:-}
SPOOL=/realm/state/agentctl/events.jsonl
BOARD=/realm/tmp/work/campaign-board.json
for _ in $(seq 1 240); do
  state=$(gh pr view "$PR" -R "$REPO" --json state --jq .state 2>/dev/null) || state=""
  case "$state" in
    MERGED|CLOSED) break ;;
    OPEN|"") sleep 30 ;;
  esac
done
if [ "$state" = "OPEN" ]; then state=TIMEOUT; fi
if [ "$state" = "MERGED" ] && [ -n "$BEAD" ] && [ -f "$REASON_FILE" ]; then
  (bd close "$BEAD" --force --actor claude-overseer --reason "$(cat "$REASON_FILE")") \
    && closed=true || closed=false
else
  closed=skipped
fi
python3 - "$BOARD" "$PR" "$state" "$BEAD" "$closed" <<'PYEOF'
import json, sys, time, pathlib
board_path, pr, state, bead, closed = sys.argv[1:6]
p = pathlib.Path(board_path)
try: board = json.loads(p.read_text())
except Exception: board = {"prs": {}, "lanes": {}, "updated": None}
board.setdefault("prs", {})[pr] = {"state": state, "bead": bead or None, "bead_closed": closed}
board["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
p.write_text(json.dumps(board, indent=1, sort_keys=True))
PYEOF
printf '{"kind":"merge_close","pr":"%s","state":"%s","bead":"%s","bead_closed":"%s","repo":"%s"}\n' \
  "$PR" "$state" "$BEAD" "$closed" "$REPO" >> "$SPOOL"
