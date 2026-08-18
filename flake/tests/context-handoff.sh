#!/usr/bin/env bash
# Provably fails when: the handoff record is written world-readable, or stops
# excluding transcript/environment content.

set -euo pipefail

writer="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/repo" "$test_root/global"
git -C "$test_root/repo" init -q

payload() {
  local client="$1"
  printf '%s\n' "{\"cwd\":\"$test_root/repo\",\"client\":\"$client\",\"handoff\":{\"mission\":\"same mission\",\"bead_ids\":[\"sinnix-ac1\"],\"active_jobs\":[\"job-1\"],\"completed_verification\":[\"fixture\"],\"evidence_paths\":[\"flake/tests\"],\"blockers\":[\"lease\"],\"next_action\":\"resume\"}}"
}

claude_record="$(payload claude | "$writer")"
codex_record="$(payload codex | "$writer")"

test -f "$claude_record" -a -f "$codex_record"
test "$(stat -c '%a' "$claude_record")" = 600
test "$(stat -c '%a' "$(dirname "$claude_record")")" = 700
diff -u <(sed -n '2,/^---$/p' "$claude_record" | cut -d: -f1 | sort) <(sed -n '2,/^---$/p' "$codex_record" | cut -d: -f1 | sort)
grep -Fq 'mission: "same mission"' "$claude_record"
grep -Fq 'bead_ids: ["sinnix-ac1"]' "$claude_record"
if grep -Fq 'transcript' "$claude_record"; then
  echo "handoff leaked transcript content" >&2
  exit 1
fi

global_input="$(jq -nc '{cwd:"/nowhere",client:"codex",handoff:{mission:"global"}}')"
global_record="$(printf '%s\n' "$global_input" | CLAUDE_SCRATCH_ROOT="$test_root/global" "$writer")"
test "$(dirname "$global_record")" = "$test_root/global"
grep -Fq 'repo_root: ""' "$global_record"
grep -Fq 'dirty_paths: []' "$global_record"
