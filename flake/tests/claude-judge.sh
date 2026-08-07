#!/usr/bin/env bash
set -euo pipefail

judge=$1
review_helper=${2:-}
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/receipts" "$test_root/context"

cat >"$test_root/bin/fake-claude" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
count_file=${CLAUDE_JUDGE_COUNT:?}
count=0
[[ -f "$count_file" ]] && count=$(<"$count_file")
count=$((count + 1))
printf '%s' "$count" >"$count_file"
printf '%s\n' "$*" >>"${CLAUDE_JUDGE_ARGS:?}"
if [[ ${CLAUDE_JUDGE_MODE:-valid} == transport ]]; then
  echo 'transport failure' >&2
  exit 7
fi
if [[ ${CLAUDE_JUDGE_MODE:-valid} == signal ]]; then
  printf '%s' "$$" >"${CLAUDE_JUDGE_SIGNAL_MARKER:?}"
  trap 'exit 143' TERM
  sleep 30
fi
if [[ ${CLAUDE_JUDGE_MODE:-valid} == invalid-once && $count == 1 ]]; then
  printf '%s\n' '{"session_id":"session-1","model":"fixture","result":{"verdict":7}}'
else
  printf '%s\n' '{"session_id":"session-1","model":"fixture","usage":{"input_tokens":3,"output_tokens":2},"total_cost_usd":0.01,"result":{"verdict":"allow"}}'
fi
EOF
chmod +x "$test_root/bin/fake-claude"

cat >"$test_root/schema.json" <<'EOF'
{"type":"object","properties":{"verdict":{"type":"string"}},"required":["verdict"],"additionalProperties":false}
EOF
printf 'bounded context\n' >"$test_root/context/ok.txt"

run_judge() {
  CLAUDE_JUDGE_COUNT="$test_root/count" \
    CLAUDE_JUDGE_ARGS="$test_root/args" \
    SINNIX_CLAUDE_JUDGE_BIN="$test_root/bin/fake-claude" \
    XDG_STATE_HOME="$test_root/state" \
    "$judge" --schema "$test_root/schema.json" --context "$test_root/context/ok.txt" --receipt-dir "$test_root/receipts" -- "$@"
}

test "$(run_judge 'return a verdict')" = '{"verdict":"allow"}'
jq -e '.outcome == "passed" and .attempts == [{number:1,exit_status:0,stderr_bytes:0,validation:"passed"}] and .session_id == "session-1" and .total_cost_usd == 0.01' \
  "$test_root"/receipts/*.json >/dev/null
test "$(stat -c %a "$test_root/receipts"/*.json)" = 600

: >"$test_root/args"
: >"$test_root/count"
test "$(CLAUDE_JUDGE_MODE=invalid-once run_judge 'retry this verdict')" = '{"verdict":"allow"}'
test "$(<"$test_root/count")" = 2
grep -F -- '--resume session-1' "$test_root/args"
jq -e '.attempts | length == 2 and .[0].validation == "failed" and .[1].validation == "passed"' \
  "$test_root"/receipts/*.json >/dev/null

: >"$test_root/args"
: >"$test_root/count"
if CLAUDE_JUDGE_MODE=transport run_judge 'do not retry transport' >/dev/null 2>"$test_root/transport.err"; then
  echo 'transport failure unexpectedly passed' >&2
  exit 1
fi
test "$(<"$test_root/count")" = 1

: >"$test_root/signal-marker"
CLAUDE_JUDGE_MODE=signal CLAUDE_JUDGE_SIGNAL_MARKER="$test_root/signal-marker" run_judge 'terminate the child group' >/dev/null 2>"$test_root/signal.err" &
judge_pid=$!
sleep 0.2
kill -TERM "$judge_pid"
set +e
wait "$judge_pid"
signal_status=$?
set -e
test "$signal_status" = 143
! kill -0 "$(<"$test_root/signal-marker")" 2>/dev/null

if SINNIX_CLAUDE_JUDGE_BIN="$test_root/bin/fake-claude" "$judge" --schema "$test_root/schema.json" --context "$test_root/context/missing.txt" --receipt-dir "$test_root/receipts" -- 'reject missing context' >/dev/null 2>&1; then
  echo 'missing context unexpectedly passed' >&2
  exit 1
fi
if printf '%*s' 20 x >"$test_root/context/large.txt" && SINNIX_CLAUDE_JUDGE_BIN="$test_root/bin/fake-claude" "$judge" --schema "$test_root/schema.json" --context "$test_root/context/large.txt" --max-context-bytes 4 --receipt-dir "$test_root/receipts" -- 'reject large context' >/dev/null 2>&1; then
  echo 'large context unexpectedly passed' >&2
  exit 1
fi

if [[ -n $review_helper ]]; then
  mkdir -p "$test_root/review-bin"
  cp "$judge" "$test_root/review-bin/sinnix-claude-judge"
  chmod +x "$test_root/review-bin/sinnix-claude-judge"
  PATH="$test_root/review-bin:$PATH" \
    CLAUDE_JUDGE_COUNT="$test_root/review-count" \
    CLAUDE_JUDGE_ARGS="$test_root/review-args" \
    SINNIX_CLAUDE_JUDGE_BIN="$test_root/bin/fake-claude" \
    XDG_STATE_HOME="$test_root/state" \
    "$review_helper" "$test_root/schema.json" "$test_root/context/ok.txt" -- 'review through shared wrapper' >/dev/null
fi

echo 'claude-judge fixture passed'
