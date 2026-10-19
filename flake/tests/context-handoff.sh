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

# Hold both writers immediately before publication, after each chose its name.
mkdir -p "$test_root/bin" "$test_root/barrier" "$test_root/concurrent" "$test_root/collision"
real_mv=$(command -v mv)
real_date=$(command -v date)
printf '#!%s\n' "$BASH" >"$test_root/bin/mv"
cat >>"$test_root/bin/mv" <<'WRAPPER'
set -euo pipefail
if [ "$HANDOFF_TEST_MODE" = collision ]; then
  printf 'retained preexisting record\n' > "${@: -1}"
else
  touch "$HANDOFF_BARRIER/$$"
  for ((attempt=0; attempt<500; attempt++)); do
    markers=("$HANDOFF_BARRIER"/*)
    [ "${#markers[@]}" -ge 2 ] && break
    sleep 0.01
  done
  [ "${#markers[@]}" -ge 2 ] || exit 99
fi
exec "$REAL_MV" "$@"
WRAPPER
printf '#!%s\n' "$BASH" >"$test_root/bin/date"
cat >>"$test_root/bin/date" <<'WRAPPER'
if [ "${2:-}" = +%Y%m%dT%H%M%SZ ]; then
  echo 20260101T000000Z
else
  exec "$REAL_DATE" "$@"
fi
WRAPPER
chmod +x "$test_root/bin/mv" "$test_root/bin/date"
for session in one two; do
  jq -nc --arg session "$session" '{session_id:$session,cwd:"/nowhere",trigger:"auto"}' >"$test_root/$session.json"
done
for session in one two; do
  env PATH="$test_root/bin:$PATH" REAL_MV="$real_mv" REAL_DATE="$real_date" \
    HANDOFF_TEST_MODE=concurrent HANDOFF_BARRIER="$test_root/barrier" \
    CLAUDE_SCRATCH_ROOT="$test_root/concurrent" \
    "$writer" <"$test_root/$session.json" >"$test_root/$session.out" &
  if [ "$session" = one ]; then first_pid=$!; else second_pid=$!; fi
done
wait "$first_pid"
wait "$second_pid"
one_record=$(cat "$test_root/one.out")
two_record=$(cat "$test_root/two.out")
if [ "$one_record" = "$two_record" ]; then
  echo "concurrent handoffs published the same record path" >&2
  exit 1
fi
grep -Fq 'session_id: "one"' "$one_record"
grep -Fq 'session_id: "two"' "$two_record"
test "$(stat -c '%a' "$one_record")" = 600
test "$(stat -c '%a' "$two_record")" = 600

# Even a competing final name introduced after staging cannot be overwritten.
if env PATH="$test_root/bin:$PATH" REAL_MV="$real_mv" REAL_DATE="$real_date" \
  HANDOFF_TEST_MODE=collision CLAUDE_SCRATCH_ROOT="$test_root/collision" \
  "$writer" <"$test_root/one.json" >"$test_root/collision.out" 2>"$test_root/collision.err"; then
  echo "handoff replaced a competing record" >&2
  exit 1
fi
shopt -s nullglob
records=("$test_root/collision"/compaction-*.md)
test "${#records[@]}" -eq 1
grep -Fxq 'retained preexisting record' "${records[0]}"
test ! -s "$test_root/collision.out"
staged=("$test_root/collision"/.compaction-*)
test "${#staged[@]}" -eq 0

# Git's line-oriented presentation quotes unusual names and joins renames.
# The handoff must retain actual path strings, not that display syntax.
original='old "file".txt'
renamed=$'new\tname.txt'
untracked=$'line\n雪\\name.txt'
printf 'neutral fixture\n' >"$test_root/repo/$original"
git -C "$test_root/repo" add -- "$original"
git -C "$test_root/repo" -c user.name=Fixture -c user.email=fixture@example.invalid \
  -c commit.gpgsign=false commit -qm 'neutral fixture'
git -C "$test_root/repo" mv -- "$original" "$renamed"
printf 'neutral untracked fixture\n' >"$test_root/repo/$untracked"
path_record="$(payload claude | "$writer")"
paths="$(grep '^dirty_paths: ' "$path_record")"
paths="${paths#dirty_paths: }"
jq -e --arg original "$original" --arg renamed "$renamed" --arg untracked "$untracked" \
  'index($original) != null and index($renamed) != null and index($untracked) != null' \
  <<<"$paths" >/dev/null
