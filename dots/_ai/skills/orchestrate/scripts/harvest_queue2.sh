#!/usr/bin/env bash
# Two-phase mechanical harvest for a finished polylogue lane worktree.
# Usage: harvest_queue2.sh <worktree> <commit-title> <pr-body-file> [<bead-id> <close-reason-file>]
#
# Phase A (parallel, 4-slot gate semaphore, no repo flock):
#   fetch (under a short fetch-lock) -> absorb uncommitted work -> rebase onto
#   origin/master (halts on conflict) -> quick gate with one mechanical
#   baseline-displacement retry. The expensive gate runs concurrently across
#   harvests instead of serializing behind one repo flock.
# Phase B (repo flock, seconds): if master moved since the gate ran, re-rebase
#   and re-gate; then push -> PR -> auto-merge armed -> merge watcher.
#
# Receipt discipline: passing a bead REQUIRES the reason file to carry a
# literal "DISPOSITION: close" line — a slice receipt without it is refused at
# queue time instead of closing a bead that says "stays open".
# Prints "HARVEST-OK pr=<num> branch=<branch>" on success; nonzero + reason otherwise.
set -u
WT=$1
TITLE=$2
BODY=$3
BEAD=${4:-}
REASON=${5:-}
REPO=/realm/project/polylogue
LOCK=/realm/tmp/work/.harvest-git.flock
FETCHLOCK=/realm/tmp/work/.harvest-fetch.flock
DEV=(nix develop --accept-flake-config --command)

# Every harvest terminal reaches the one event stream. Five finished lanes
# silently never published on 2026-08-26 because harvest outcomes lived only in
# a log nobody was prompted to read (the worker contract's "orphan obligations"
# smell). The monitor now surfaces failures without anyone polling.
emit_harvest_event() {
  local phase=$1 detail=$2
  python3 - "$phase" "$detail" "$WT" "$BEAD" <<'PYEMIT' 2>/dev/null || true
import json, os, sys, datetime
phase, detail, wt, bead = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
row = {
    "kind": "harvest",
    "phase": phase,
    "worktree": os.path.basename(wt),
    "bead": bead or None,
    "detail": detail[:400],
    "project": "polylogue",
    "completed_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
    "schema_version": 1,
}
with open("/realm/state/agentctl/events.jsonl", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(row, sort_keys=True) + "\n")
PYEMIT
}

if [ -n "$BEAD" ]; then
  [ -f "$REASON" ] || {
    emit_harvest_event failed "HARVEST-FAIL no reason file for \$BEAD"
    echo "HARVEST-FAIL no reason file for $BEAD"
    exit 5
  }
  grep -q '^DISPOSITION: close' "$REASON" || {
    emit_harvest_event failed "HARVEST-FAIL receipt for \$BEAD lacks 'DISPOSITION: close' — slice receipts queue without bead args"
    echo "HARVEST-FAIL receipt for $BEAD lacks 'DISPOSITION: close' — slice receipts queue without bead args"
    exit 5
  }
fi

cd "$WT" || {
  emit_harvest_event failed "HARVEST-FAIL no worktree"
  echo "HARVEST-FAIL no worktree"
  exit 2
}

# Exclusive per-worktree claim held for the whole harvest. dispatch_lane checks
# this before launching, so a completion lane can no longer race a rebase/amend
# /push on the same branch (2026-08-26).
WTLOCK="/realm/tmp/work/.wt-$(basename "$WT").lock"
exec 8>"$WTLOCK"
flock -n 8 || {
  emit_harvest_event failed "HARVEST-FAIL worktree busy (another harvest holds \$WTLOCK)"
  echo "HARVEST-FAIL worktree busy (another harvest holds $WTLOCK)"
  exit 6
}

fetch_locked() { flock -w 120 "$FETCHLOCK" git fetch -q origin; }
fetch_locked || {
  emit_harvest_event failed "HARVEST-FAIL fetch"
  echo "HARVEST-FAIL fetch"
  exit 2
}

if ! git diff --quiet || ! git diff --cached --quiet; then
  "${DEV[@]}" ruff format polylogue/ tests/ devtools/ >/dev/null 2>&1
  "${DEV[@]}" ruff check --fix polylogue/ tests/ devtools/ >/dev/null 2>&1
  git add -A . 2>/dev/null
  git -C "$WT" commit -q -m "$TITLE" || {
    emit_harvest_event failed "HARVEST-FAIL commit"
    echo "HARVEST-FAIL commit"
    exit 2
  }
fi

if ! git rebase -q origin/master; then
  git rebase --abort 2>/dev/null
  emit_harvest_event failed "HARVEST-FAIL rebase conflict (human resolves)"
  echo "HARVEST-FAIL rebase conflict (human resolves)"
  exit 3
fi
GATED_AT=$(git rev-parse origin/master)

# --- Phase A gate under a 4-slot semaphore -------------------------------
QLOG="/realm/tmp/work/harvest-$(basename "$WT").quick.log"
gate() { (cd "$WT" && "${DEV[@]}" devtools verify --quick >"$QLOG" 2>&1); }
# Mechanical remedies applied once before declaring a gate failure. Generated
# surfaces drifting out of sync accounted for 3 of 15 stuck harvests on
# 2026-08-26 and are regenerable, not judgment.
mechanical_render() {
  grep -q "render all ... FAILED\|out of sync" "$QLOG" 2>/dev/null || return 1
  (cd "$WT" && "${DEV[@]}" devtools render all >/dev/null 2>&1) || return 1
  git -C "$WT" diff --quiet && return 1
  git -C "$WT" add -A . && git -C "$WT" commit -q --amend --no-edit
}

run_gate() {
  if ! gate; then
    python3 /home/sinity/.claude/skills/review-land/scripts/rebase_baselines.py "$QLOG" &&
      git add devtools/patterns/baselines/ && git -C "$WT" commit -q --amend --no-edit && gate && return 0
    mechanical_render && gate && return 0
    return 1
  fi
}

slot_fd=""
while [ -z "$slot_fd" ]; do
  for i in 1 2 3 4; do
    exec {fd}>"/realm/tmp/work/.gate-slot-$i.lock"
    if flock -n "$fd"; then
      slot_fd=$fd
      break
    fi
    exec {fd}>&-
  done
  [ -z "$slot_fd" ] && sleep 15
done
run_gate || {
  emit_harvest_event failed "HARVEST-FAIL quick gate — see \$QLOG"
  echo "HARVEST-FAIL quick gate — see $QLOG"
  exit 3
}
exec {slot_fd}>&-

# --- Phase B publish under the repo flock --------------------------------
exec 9>"$LOCK"
flock -w 900 9 || {
  emit_harvest_event failed "HARVEST-FAIL flock timeout"
  echo "HARVEST-FAIL flock timeout"
  exit 4
}

for lockfile in "$REPO"/.git/index.lock "$REPO"/.git/worktrees/*/index.lock; do
  [ -f "$lockfile" ] || continue
  if [ ! -s "$lockfile" ] && [ -z "$(find "$lockfile" -newermt '-3 minutes')" ] && ! pgrep -x git >/dev/null; then
    rm -f "$lockfile" && echo "cleared stale lock: $lockfile"
  fi
done

fetch_locked
if [ "$(git rev-parse origin/master)" != "$GATED_AT" ]; then
  if ! git rebase -q origin/master; then
    git rebase --abort 2>/dev/null
    emit_harvest_event failed "HARVEST-FAIL rebase conflict (human resolves)"
    echo "HARVEST-FAIL rebase conflict (human resolves)"
    exit 3
  fi
  run_gate || {
    emit_harvest_event failed "HARVEST-FAIL quick gate after master moved — see \$QLOG"
    echo "HARVEST-FAIL quick gate after master moved — see $QLOG"
    exit 3
  }
fi

git push -qf -u origin HEAD || {
  emit_harvest_event failed "HARVEST-FAIL push"
  echo "HARVEST-FAIL push"
  exit 2
}
PR=$(gh pr create --title "$TITLE" --body-file "$BODY" 2>&1 | tail -1)
NUM=${PR##*/}
case "$NUM" in '' | *[!0-9]*)
  emit_harvest_event failed "HARVEST-FAIL pr-create: \$PR"
  echo "HARVEST-FAIL pr-create: $PR"
  exit 2
  ;;
esac
# Arm auto-merge and VERIFY it armed: silent arming failures have left
# green, CLEAN PRs sitting open (observed on #4280 and #4282).
gh pr merge "$NUM" --squash --auto >/dev/null 2>&1 || true
if [ "$(gh pr view "$NUM" --json autoMergeRequest -q '.autoMergeRequest != null' 2>/dev/null)" != "true" ]; then
  echo "HARVEST-WARN auto-merge did not arm for pr=$NUM (merge manually when checks pass)"
fi
nohup /home/sinity/.claude/skills/review-land/scripts/merge_close.sh \
  Sinity/polylogue "$NUM" $BEAD $REASON >"/realm/tmp/work/merge-$NUM.log" 2>&1 &
emit_harvest_event published "pr=$NUM"
echo "HARVEST-OK pr=$NUM branch=$(git rev-parse --abbrev-ref HEAD)"
