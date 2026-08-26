#!/usr/bin/env bash
# Publish a completed lane from its durable remote branch ref.
# Usage: harvest_queue2.sh <branch> <commit-title> <pr-body-file> [<bead-id> <close-reason-file>]
# The lane owns rebase, verification, and push. Harvest never opens the lane
# checkout; CI is the verification authority for the PR.
set -u
BRANCH=${1:?branch is required}
TITLE=${2:?title is required}
BODY=${3:?body file is required}
BEAD=${4:-}
REASON=${5:-}
REPO=/realm/project/polylogue
SPOOL=/realm/state/agentctl/events.jsonl

case "$BRANCH" in
  ''|master|main|*' '*|*'..'*|*'~'*|*'^'*|*':'*|*'?'*|*'['*|*'\\'*|*'//'*)
    echo "HARVEST-FAIL invalid branch ref: $BRANCH" >&2; exit 2 ;;
esac
if [ -n "$BEAD" ]; then
  [ -f "$REASON" ] || { echo "HARVEST-FAIL no reason file for $BEAD"; exit 5; }
  grep -q '^DISPOSITION: close' "$REASON" || {
    echo "HARVEST-FAIL receipt for $BEAD lacks 'DISPOSITION: close'"; exit 5;
  }
fi

emit() {
  local phase=$1 detail=$2
  python3 - "$phase" "$detail" "$BRANCH" "$BEAD" "$SPOOL" <<'PY'
import datetime, json, sys
phase, detail, branch, bead, spool = sys.argv[1:]
row = {"kind": "harvest", "phase": phase, "branch": branch,
       "bead": bead or None, "detail": detail[:400], "project": "polylogue",
       "completed_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
       "schema_version": 1}
try:
    with open(spool, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
except OSError:
    pass
PY
}

remote=$(git -C "$REPO" ls-remote origin "refs/heads/$BRANCH" 2>&1) || {
  emit failed "HARVEST-FAIL remote ref lookup: $remote"
  echo "HARVEST-FAIL remote ref lookup: $remote"; exit 2
}
[ -n "$remote" ] || {
  emit failed "HARVEST-FAIL branch is not pushed: $BRANCH"
  echo "HARVEST-FAIL branch is not pushed: $BRANCH"; exit 2
}
if ! pr_output=$(gh pr create --repo Sinity/polylogue --head "$BRANCH" \
    --title "$TITLE" --body-file "$BODY" 2>&1); then
  emit failed "HARVEST-FAIL pr-create: $pr_output"
  echo "HARVEST-FAIL pr-create: $pr_output"; exit 2
fi
PR=${pr_output##*/}
case "$PR" in ''|*[!0-9]*)
  emit failed "HARVEST-FAIL malformed PR response: $pr_output"
  echo "HARVEST-FAIL malformed PR response: $pr_output"; exit 2 ;;
esac
gh pr merge "$PR" --repo Sinity/polylogue --squash --auto >/dev/null 2>&1 || true
if [ "$(gh pr view "$PR" --repo Sinity/polylogue --json autoMergeRequest \
    -q '.autoMergeRequest != null' 2>/dev/null)" != true ]; then
  echo "HARVEST-WARN auto-merge did not arm for pr=$PR (merge manually when checks pass)"
fi
emit published "pr=$PR"
echo "HARVEST-OK pr=$PR branch=$BRANCH"
