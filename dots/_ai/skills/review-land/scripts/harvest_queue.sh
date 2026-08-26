#!/usr/bin/env bash
# Mechanical harvest pipeline for a finished polylogue lane worktree.
# Usage: harvest_queue.sh <worktree> <commit-title> <pr-body-file> [<bead-id> <close-reason-file>]
# With bead args, the merge watcher records the decision-time receipt in the
# event spool; sinnixd-reactor closes the bead and updates the board on merge.
#
# Does everything EXCEPT the adversarial diff review (do that before calling):
#   flock-serialized against other harvests -> stale-lock hygiene ->
#   fetch + rebase onto origin/master (halts on conflict) ->
#   commit uncommitted work (auto format/lint-fix) -> quick gate
#   (one mechanical baseline-displacement pass, as harvest_lane.sh) ->
#   push -> PR -> gh auto-merge armed, merge_on_green fallback watcher.
# Prints "HARVEST-OK pr=<num> branch=<branch>" on success; nonzero + reason otherwise.
set -u
WT=$1; TITLE=$2; BODY=$3; BEAD=${4:-}; REASON=${5:-}
REPO=/realm/project/polylogue
LOCK=/realm/tmp/work/.harvest-git.flock
DEV=(nix develop --accept-flake-config --command)

exec 9>"$LOCK"
flock -w 900 9 || { echo "HARVEST-FAIL flock timeout"; exit 4; }

# Stale-lock hygiene: zero-byte index locks older than 3 min with no live git.
for lockfile in "$REPO"/.git/index.lock "$REPO"/.git/worktrees/*/index.lock; do
  [ -f "$lockfile" ] || continue
  if [ ! -s "$lockfile" ] && [ -z "$(find "$lockfile" -newermt '-3 minutes')" ] && ! pgrep -x git >/dev/null; then
    rm -f "$lockfile" && echo "cleared stale lock: $lockfile"
  fi
done

cd "$WT" || { echo "HARVEST-FAIL no worktree"; exit 2; }
git fetch -q origin || { echo "HARVEST-FAIL fetch"; exit 2; }

if ! git diff --quiet || ! git diff --cached --quiet; then
  "${DEV[@]}" ruff format polylogue/ tests/ devtools/ >/dev/null 2>&1
  "${DEV[@]}" ruff check --fix polylogue/ tests/ devtools/ >/dev/null 2>&1
  git add -A . 2>/dev/null
  git -C "$WT" commit -q -m "$TITLE" || { echo "HARVEST-FAIL commit"; exit 2; }
fi

if ! git rebase -q origin/master; then
  git rebase --abort 2>/dev/null
  echo "HARVEST-FAIL rebase conflict (human resolves)"; exit 3
fi

QLOG="/realm/tmp/work/harvest-$(basename "$WT").quick.log"
gate() { (cd "$WT" && "${DEV[@]}" devtools verify --quick >"$QLOG" 2>&1); }
if ! gate; then
  python3 /home/sinity/.claude/skills/review-land/scripts/rebase_baselines.py "$QLOG" \
    && git add devtools/patterns/baselines/ && git -C "$WT" commit -q --amend --no-edit && gate \
    || { echo "HARVEST-FAIL quick gate — see $QLOG"; exit 3; }
fi

git push -qf -u origin HEAD || { echo "HARVEST-FAIL push"; exit 2; }
PR=$(gh pr create --title "$TITLE" --body-file "$BODY" 2>&1 | tail -1)
NUM=${PR##*/}
case "$NUM" in ''|*[!0-9]*) echo "HARVEST-FAIL pr-create: $PR"; exit 2;; esac
gh pr merge "$NUM" --squash --auto >/dev/null 2>&1 || true
# Reactor watcher: merges are reported to the spool with the decision-time
# receipt; sinnixd-reactor performs the typed close and board reaction.
nohup /home/sinity/.claude/skills/review-land/scripts/merge_close.sh \
  Sinity/polylogue "$NUM" $BEAD $REASON >"/realm/tmp/work/merge-$NUM.log" 2>&1 &
echo "HARVEST-OK pr=$NUM branch=$(git rev-parse --abbrev-ref HEAD)"
