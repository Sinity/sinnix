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

# Dispose the worktree at merge time so clutter never accumulates (2026-08-26:
# 138 worktrees had piled up, 77 of them long-landed). Guards: only when the PR
# actually MERGED, the tree is clean, no process has its cwd inside, and no
# non-terminal job owns it. A worktree that shipped this PR and then accumulated
# NEW unpublished commits is kept -- disposal must never race a later slice.
# Belongs in the reactor; lives here until sinnix-235w ships agentctl campaign gc.
dispose_worktree_if_landed() {
  local wt=$1 repo=$2
  [ -d "$wt" ] || return 0
  [ -n "$(git -C "$wt" status --porcelain 2>/dev/null)" ] && {
    echo "dispose-skip dirty $wt"
    return 0
  }
  for c in /proc/[0-9]*/cwd; do
    t=$(readlink "$c" 2>/dev/null) || continue
    case "$t" in "$wt" | "$wt"/*)
      echo "dispose-skip live-cwd $wt"
      return 0
      ;;
    esac
  done
  git -C "$wt" fetch -q origin 2>/dev/null
  local files differing
  files=$(git -C "$wt" diff origin/master...HEAD --name-only 2>/dev/null)
  if [ -n "$files" ]; then
    differing=$(git -C "$wt" diff origin/master HEAD --name-only -- $files 2>/dev/null | grep -c .)
    [ "$differing" -gt 0 ] && {
      echo "dispose-skip unpublished-content($differing) $wt"
      return 0
    }
  fi
  local branch
  branch=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)
  git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 &&
    {
      [ -n "$branch" ] && [ "$branch" != master ] && git -C "$repo" branch -D "$branch" >/dev/null 2>&1
      echo "disposed $wt"
    }
}

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

if [ "$state" = "MERGED" ]; then
  # REPO is the GitHub slug (owner/name); the local checkout is /realm/project/<name>.
  REPO_PATH="/realm/project/${REPO##*/}"
  BRANCH=$(gh pr view "$PR" -R "$REPO" --json headRefName --jq .headRefName 2>/dev/null)
  if [ -n "${BRANCH:-}" ] && [ -d "$REPO_PATH" ]; then
    WT_PATH=$(git -C "$REPO_PATH" worktree list --porcelain 2>/dev/null |
      awk -v b="refs/heads/$BRANCH" '/^worktree /{w=$2} /^branch /{if ($2==b) print w}')
    [ -n "${WT_PATH:-}" ] && dispose_worktree_if_landed "$WT_PATH" "$REPO_PATH"
  fi
fi
