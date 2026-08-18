#!/usr/bin/env bash
# Provably fails when: the sampler stops de-duplicating a candidate or a
# judgment, or its report stops deriving the review counters.
set -euo pipefail

sampler=$1
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/home" "$test_root/state" "$test_root/bin"

transcript="$test_root/transcript.jsonl"
payload=$(jq -nc --arg transcript "$transcript" '{session_id:"fixture-session",event_id:"fixture-stop",transcript_path:$transcript,duration_ms:1000,status:"completed",last_assistant_message:"finished"}')
printf '%s' "$payload" | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" SINNIX_VACUITY_SAMPLE_RATE=1 "$sampler" enqueue
printf '%s' "$payload" | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" SINNIX_VACUITY_SAMPLE_RATE=1 "$sampler" enqueue
test "$(jq -s '[.[] | select(.type == "vacuity_candidate")] | length' "$test_root/state/claude-code/dispatch-ledger.jsonl")" = 1

printf '%s\n' '{"role":"assistant","content":"finished"}' >"$transcript"
cat >"$test_root/bin/fake-judge" <<'EOF'
printf '%s\n' '{"verdict":"unsupported","confidence":0.2,"evidence":["fixture:transcript"],"refutation_attempted":true,"unsupported":["fixture evidence"]}'
EOF
sed -i "1i#!$(command -v bash)" "$test_root/bin/fake-judge"
chmod +x "$test_root/bin/fake-judge"
HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" SINNIX_CLAUDE_JUDGE="$test_root/bin/fake-judge" PATH="$test_root/bin:$PATH" "$sampler" judge-once
HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" SINNIX_CLAUDE_JUDGE="$test_root/bin/fake-judge" PATH="$test_root/bin:$PATH" "$sampler" judge-once
test "$(jq -s '[.[] | select(.type == "vacuity_judgment")] | length' "$test_root/state/claude-code/dispatch-ledger.jsonl")" = 1
candidate_id=$(jq -r 'select(.type == "vacuity_candidate") | .candidate_id' "$test_root/state/claude-code/dispatch-ledger.jsonl")
HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$sampler" review --candidate-id "$candidate_id" --label false_positive
HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$sampler" report | jq -e '.denominator == 1 and .sampled == 1 and .judged == 1 and .verdict_distribution.unsupported == 1' >/dev/null
HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$sampler" report | jq -e '.reviewed_count == 1 and .reviewed_false_positive_rate == 1' >/dev/null
echo 'vacuity sampler fixture passed'
