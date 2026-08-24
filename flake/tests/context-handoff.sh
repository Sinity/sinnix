#!/usr/bin/env bash
# Provably fails when: the handoff record is written world-readable, stops
# recording the session binding the real PreCompact payload carries, or
# starts leaking transcript content into the record.

set -euo pipefail

writer="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

mkdir -p "$test_root/repo" "$test_root/global"
git -C "$test_root/repo" init -q

# Real transcript with a sentinel: the record must point at it, never quote it.
transcript="$test_root/sess-1234.jsonl"
printf '%s\n' '{"type":"user","message":{"content":"SENTINEL-DO-NOT-LEAK"}}' >"$transcript"

payload() {
  local client="$1"
  jq -nc --arg cwd "$test_root/repo" --arg tp "$transcript" --arg client "$client" \
    '{session_id:"sess-1234",transcript_path:$tp,cwd:$cwd,hook_event_name:"PreCompact",trigger:"auto",custom_instructions:"",client:$client}'
}

claude_record="$(payload claude | "$writer")"
codex_record="$(payload codex | "$writer")"

test -f "$claude_record" -a -f "$codex_record"
test "$(stat -c '%a' "$claude_record")" = 600
test "$(stat -c '%a' "$(dirname "$claude_record")")" = 700
diff -u <(sed -n '2,/^---$/p' "$claude_record" | cut -d: -f1 | sort) <(sed -n '2,/^---$/p' "$codex_record" | cut -d: -f1 | sort)
grep -Fq 'session_id: "sess-1234"' "$claude_record"
grep -Fq 'trigger: "auto"' "$claude_record"
grep -Fq "transcript_path: \"$transcript\"" "$claude_record"
if grep -Fq 'SENTINEL-DO-NOT-LEAK' "$claude_record"; then
  echo "handoff leaked transcript content" >&2
  exit 1
fi

global_input="$(jq -nc '{session_id:"sess-9",transcript_path:"/nowhere/t.jsonl",cwd:"/nowhere",client:"codex",trigger:"manual"}')"
global_record="$(printf '%s\n' "$global_input" | CLAUDE_SCRATCH_ROOT="$test_root/global" "$writer")"
test "$(dirname "$global_record")" = "$test_root/global"
grep -Fq 'repo_root: ""' "$global_record"
grep -Fq 'dirty_paths: []' "$global_record"
