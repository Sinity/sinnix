#!/usr/bin/env bash
# Proves that the pinned Beads binary reads its Dolt authority, not a mutable
# JSONL export, during ordinary read-only operations.

set -euo pipefail

bd="$1"
test_root="$(mktemp -d "${TMPDIR:?}/bd-dolt-authority.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT
export HOME="$test_root/home"
mkdir -p "$HOME" "$test_root/repo"
git init --quiet "$test_root/repo"

git -C "$test_root/repo" config user.name fixture
git -C "$test_root/repo" config user.email fixture@example.invalid
printf 'fixture\n' >"$test_root/repo/README.md"
git -C "$test_root/repo" add README.md
git -C "$test_root/repo" commit --quiet -m fixture
(
  cd "$test_root/repo"
  "$bd" init --non-interactive --prefix fixture --skip-hooks --skip-agents >/dev/null
  created="$("$bd" --json create "Dolt authority fixture")"
  issue_id="$(printf '%s' "$created" | jq -r 'if type == "array" then .[0].id else .id end')"
  test -n "$issue_id"
  "$bd" export -o .beads/issues.jsonl >/dev/null

  normalize_issue='if type == "array" then .[0] else . end | {id, title, status}'
  before="$("$bd" --readonly --json show "$issue_id" | jq -c "$normalize_issue")"
  workspace="$("$bd" --readonly --json where | jq -r .path)"
  database="$("$bd" --readonly --json where | jq -r .database_path)"
  test "$(realpath "$workspace")" = "$(realpath "$test_root/repo/.beads")"
  test -d "$database"

  git worktree add --quiet -b fixture-linked "$test_root/linked"
  linked_workspace="$("$bd" --directory "$test_root/linked" --readonly --json where | jq -r .path)"
  linked_database="$("$bd" --directory "$test_root/linked" --readonly --json where | jq -r .database_path)"
  test "$(realpath "$linked_workspace")" = "$(realpath "$workspace")"
  test "$(realpath "$linked_database")" = "$(realpath "$database")"

  jq --arg issue_id "$issue_id" 'if .id == $issue_id then .title = "forged JSONL export" else . end' \
    .beads/issues.jsonl >.beads/issues.jsonl.tmp
  mv .beads/issues.jsonl.tmp .beads/issues.jsonl

  after="$("$bd" --readonly --json show "$issue_id" | jq -c "$normalize_issue")"
  test "$before" = "$after"
)
