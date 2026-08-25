#!/usr/bin/env bash
# Gate-watch + merge in one background action: never leave a green PR
# waiting to be lapped by the merge train. Run via Bash run_in_background.
# Usage: merge_on_green.sh <repo> <pr-number> [check-name-regex]
# Example: merge_on_green.sh Sinity/polylogue 4142 circleci
set -u
REPO=$1
PR=$2
RE=${3:-circleci}
while :; do
  s=$(gh pr view "$PR" --repo "$REPO" --json statusCheckRollup \
    --jq "[.statusCheckRollup[] | select((.name//.context) | test(\"$RE\")) | (.conclusion // .state)] | first" 2>/dev/null)
  [ -n "$s" ] && [ "$s" != "PENDING" ] && break
  sleep 20
done
echo "PR $PR gate=$s"
if [ "$s" = "SUCCESS" ]; then
  gh pr merge "$PR" --repo "$REPO" --squash --delete-branch 2>&1 | tail -1
  gh pr view "$PR" --repo "$REPO" --json state --jq .state
else
  echo "NOT merging: gate=$s"
  gh api "repos/$REPO/pulls/$PR/comments" --jq 'length' 2>/dev/null | sed 's/^/inline-comments=/'
fi
