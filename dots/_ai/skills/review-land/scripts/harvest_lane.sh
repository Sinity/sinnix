#!/usr/bin/env bash
# Harvest a finished polylogue lane worktree into an armed PR.
# Usage: harvest_lane.sh <worktree> <commit-title> <pr-body-file>
# Does: commit uncommitted work (title as subject), quick gate with ONE
# mechanical rebase pass for displaced pattern baselines (only when stale and
# new matches pair 1:1 within the same file), push, PR, merge_on_green.
# Refuses (exit 3) when the gate still fails after the rebase pass — a human
# decides then. Prints PR number on success.
set -u
WT=$1
TITLE=$2
BODY=$3
DEV=(nix develop --accept-flake-config --command)
cd "$WT" || exit 2

if ! git diff --quiet || ! git diff --cached --quiet; then
  # Lanes with broken envs ship unformatted/unlinted work; normalize before
  # the pre-commit hook refuses it.
  "${DEV[@]}" ruff format polylogue/ tests/ devtools/ >/dev/null 2>&1
  "${DEV[@]}" ruff check --fix polylogue/ tests/ devtools/ >/dev/null 2>&1
  # Stage the WHOLE tree: an allowlist here once dropped root-level files,
  # .agentctl/, and browser-extension/ from three merged PRs (scratch logs
  # live outside the worktree now, so -A is safe).
  git add -A . 2>/dev/null
  git commit -q -m "$TITLE" || exit 2
fi

# Scratch lives OUTSIDE the worktree: an in-tree log once reached master via
# a later `git add -A` conflict resolution.
QLOG="/realm/tmp/work/harvest-$(basename "$WT").quick.log"
gate() { (cd "$WT" && "${DEV[@]}" devtools verify --quick >"$QLOG" 2>&1); }
if ! gate; then
  python3 - "$QLOG" <<'EOF'
import json, re, sys, collections
log = open(sys.argv[1]).read()
start = log.find('"new_matches"')
if start == -1: sys.exit(1)
obj_start = log.rfind('{', 0, start)
depth = 0; end = obj_start
for i, ch in enumerate(log[obj_start:], obj_start):
    if ch == '{': depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0: end = i + 1; break
payload = json.loads(log[obj_start:end])
pat = re.compile(r'^(\S+) (\S+):(\d+)')
new = collections.defaultdict(list); stale = collections.defaultdict(list)
for row in payload.get('new_matches', []):
    m = pat.match(row); new[(m.group(1), m.group(2))].append(int(m.group(3)))
for row in payload.get('stale_matches', []):
    m = pat.match(row); stale[(m.group(1), m.group(2))].append(int(m.group(3)))
if set(new) != set(stale) or any(len(new[k]) != len(stale[k]) for k in new):
    sys.exit(1)  # not a pure displacement — human decides
for (rule, path), new_lines in new.items():
    bl = f"devtools/patterns/baselines/{rule}.txt"
    text = open(bl).read()
    for old, nw in zip(sorted(stale[(rule, path)]), sorted(new_lines)):
        o = f"{path}:{old}\n"
        if o not in text: sys.exit(1)
        text = text.replace(o, f"{path}:{nw}\n", 1)
    open(bl, 'w').write(text)
print("rebased displaced baselines")
EOF
  [ $? -eq 0 ] || {
    echo "GATE FAILED (not pure displacement) — see $QLOG"
    exit 3
  }
  git add devtools/patterns/baselines/ && git commit -q --amend --no-edit
  gate || {
    echo "GATE STILL FAILED after rebase — see $QLOG"
    exit 3
  }
fi

git push -q -u origin HEAD || exit 2
PR=$(gh pr create --title "$TITLE" --body-file "$BODY" 2>&1 | tail -1)
echo "$PR"
NUM=${PR##*/}
nohup /home/sinity/.claude/skills/review-land/scripts/merge_on_green.sh \
  Sinity/polylogue "$NUM" >"/realm/tmp/work/merge-$NUM.log" 2>&1 &
echo "merge-watch armed for #$NUM (nohup $!)"
