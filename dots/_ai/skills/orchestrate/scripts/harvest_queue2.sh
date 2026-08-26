#!/usr/bin/env bash
# Publish a completed lane through AgentCTL's typed workspace operation.
# Usage: harvest_queue2.sh <workspace-id> <job-id> <title> <body-file> [<packet-job-id> [<bead-id> <close-reason-file>]]
set -eu
WORKSPACE_ID=${1:?workspace id is required}
JOB_ID=${2:?verification job id is required}
TITLE=${3:?title is required}
BODY_FILE=${4:?body file is required}
PACKET_JOB_ID=${5:-}
BEAD=${6:-}
REASON=${7:-}
SPOOL=${HARVEST_EVENT_SPOOL:-/realm/state/agentctl/events.jsonl}

if [ -n "$BEAD" ]; then
  [ -f "$REASON" ] || {
    echo "HARVEST-FAIL no reason file for $BEAD" >&2
    exit 5
  }
  grep -q '^DISPOSITION: close' "$REASON" || {
    echo "HARVEST-FAIL receipt for $BEAD lacks 'DISPOSITION: close'" >&2
    exit 5
  }
fi
[ -f "$BODY_FILE" ] || {
  echo "HARVEST-FAIL no body file: $BODY_FILE" >&2
  exit 2
}

emit() {
  local phase=$1 detail=$2
  python3 - "$phase" "$detail" "$WORKSPACE_ID" "$BEAD" "$SPOOL" <<'PY'
import datetime
import json
import sys

phase, detail, workspace_id, bead, spool = sys.argv[1:]
row = {
    "kind": "harvest",
    "phase": phase,
    "workspace_id": workspace_id,
    "bead": bead or None,
    "detail": detail[:400],
    "project": "polylogue",
    "completed_at": datetime.datetime.now(datetime.UTC).isoformat().replace(
        "+00:00", "Z"
    ),
    "schema_version": 1,
}
try:
    with open(spool, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
except OSError:
    pass
PY
}

BODY=$(<"$BODY_FILE")
PUBLISH=(agentctl workspace publish --job "$JOB_ID" --title "$TITLE" --body "$BODY")
if [ -n "$PACKET_JOB_ID" ]; then
  PUBLISH+=(--packet-job "$PACKET_JOB_ID")
fi
PUBLISH+=(--wait "$WORKSPACE_ID")

if ! receipt=$("${PUBLISH[@]}" 2>&1); then
  emit failed "HARVEST-FAIL workspace publish: $receipt"
  echo "HARVEST-FAIL workspace publish: $receipt" >&2
  exit 2
fi
emit published "workspace publish receipt: $receipt"
echo "HARVEST-OK workspace=$WORKSPACE_ID"
