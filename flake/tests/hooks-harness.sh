#!/usr/bin/env bash
# Provably fails when: a Claude hook stops emitting the ledger row it owns
# (verified by renaming the SubagentStop dispatch_end row type), fails
# shellcheck, or blocks on a malformed payload.
set -euo pipefail

hooks_dir=$1
settings=$2
sampler=${3:-}
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/home"
ln -s /run/current-system/sw/bin/jq "$test_root/bin/jq"
ln -s /run/current-system/sw/bin/timeout "$test_root/bin/timeout"
ln -s /run/current-system/sw/bin/bash "$test_root/bin/bash"
for tool in cat date dirname mkdir sleep; do
  ln -s "/run/current-system/sw/bin/$tool" "$test_root/bin/$tool"
done
if [[ -n $sampler ]]; then
  ln -s "$sampler" "$test_root/bin/sinnix-vacuity-sampler"
  ln -s /run/current-system/sw/bin/python3 "$test_root/bin/python3"
fi

jq -e . "$settings" >/dev/null
shellcheck "$hooks_dir"/*.sh
for hook in "$hooks_dir"/*.sh; do
  bash -n "$hook"
done

run_hook() {
  local hook=$1 payload=$2
  export PATH
  printf '%s' "$payload" | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$hook"
}

model_deny=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"general-purpose","prompt":"fixture"}}')
printf '%s' "$model_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# Named agent-definition types are no longer exempt: omitting model at the
# call site is now a hard deny for every subagent_type except fork.
model_deny_named=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"review"}}')
printf '%s' "$model_deny_named" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# fork is still exempt (no output at all, allow silently).
test -z "$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"fork"}}')"
# Any dispatch that DOES carry model gets a visible confirmation systemMessage.
model_confirm=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"general-purpose","model":"sonnet"}}')
printf '%s' "$model_confirm" | jq -e '.systemMessage | contains("confirmed") and contains("sonnet")' >/dev/null
model_confirm_named=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"review","model":"opus"}}')
printf '%s' "$model_confirm_named" | jq -e '.systemMessage | contains("confirmed") and contains("opus")' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-agent-model.sh" 'not-json')"

bash_deny=$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"git push --force origin master"}}')
printf '%s' "$bash_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"printf \"safe\""}}')"
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" 'not-json' 2>/dev/null)"

# A shell glob over /nix/store makes the shell stat ~219k entries before the
# command runs; it has exhausted host memory twice. Deny the unquoted glob,
# keep concrete store paths and lazily-expanded quoted patterns working.
store_glob_payload=$(jq -n --arg c 'rg -n pattern /nix/store/*/share/doc/home-manager/*.html' '{tool_input:{command:$c}}')
store_glob_deny=$(run_hook "$hooks_dir/pretooluse-bash.sh" "$store_glob_payload")
printf '%s' "$store_glob_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
store_path_payload=$(jq -n --arg c 'cat /nix/store/abc123-foo/bin/x' '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$store_path_payload")"
store_find_payload=$(jq -n --arg c "find /nix/store -maxdepth 1 -name '*home-manager*'" '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$store_find_payload")"
# A commit message or doc describing the hazard must be able to quote the
# pattern, so heredoc bodies are exempt -- but only until the heredoc closes.
store_heredoc_body=$(printf 'git commit -F - <<%sEOF%s\nfix: a pattern like /nix/store/*/share/doc/pkg/*.html stats the whole store\nEOF\n' "'" "'")
store_heredoc_payload=$(jq -n --arg c "$store_heredoc_body" '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$store_heredoc_payload")"
store_after_heredoc=$(printf 'cat <<%sEOF%s\ntext\nEOF\nls /nix/store/*\n' "'" "'")
store_after_payload=$(jq -n --arg c "$store_after_heredoc" '{tool_input:{command:$c}}')
store_after_deny=$(run_hook "$hooks_dir/pretooluse-bash.sh" "$store_after_payload")
printf '%s' "$store_after_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null

# Empty-payload smoke call: must exit clean and silent. Runs against its
# own scratch state so its ledger rows cannot pollute the dedup/report
# counts below.
test -z "$(printf '%s' '{}' | PATH="$test_root/bin:${PATH}" HOME="$test_root/home" XDG_STATE_HOME="$test_root/state-smoke" "$hooks_dir/subagentstop-dispatch-ledger.sh")"
if [[ -n $sampler ]]; then
  payload='{"session_id":"fixture-session","event_id":"fixture-stop","transcript_path":"/missing","duration_ms":1000,"status":"completed","last_assistant_message":"finished"}'
  PATH="$test_root/bin:${PATH}" SINNIX_VACUITY_SAMPLE_RATE=1 run_hook "$hooks_dir/subagentstop-dispatch-ledger.sh" "$payload"
  PATH="$test_root/bin:${PATH}" SINNIX_VACUITY_SAMPLE_RATE=1 run_hook "$hooks_dir/subagentstop-dispatch-ledger.sh" "$payload"
  test "$(jq -s '[.[] | select(.type == "vacuity_candidate")] | length' "$test_root/state/claude-code/dispatch-ledger.jsonl")" = 1
  test "$(jq -s '[.[] | select(.type == "dispatch_end")] | length' "$test_root/state/claude-code/dispatch-ledger.jsonl")" = 2
  PATH="$test_root/bin:${PATH}" HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" sinnix-vacuity-sampler report | jq -e '.denominator == 1 and .sampled == 1 and .judged == 0' >/dev/null
fi
test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-polylogue-recall.sh" '{}')"
test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-sinex-recall.sh" '{}')"

cat >"$test_root/bin/sinexctl" <<'EOF'
#!/usr/bin/env bash
sleep 3
EOF
chmod +x "$test_root/bin/sinexctl"
PATH="$test_root/bin" SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS=1 \
  HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" \
  "$hooks_dir/sessionstart-sinex-recall.sh" </dev/null >/dev/null

mutated="$test_root/mutated-agent-model.sh"
cp "$hooks_dir/pretooluse-agent-model.sh" "$mutated"
sed -i 's/"permissionDecision": "deny"/"permissionDecision": "allow"/' "$mutated"
if printf '%s' '{"tool_input":{"subagent_type":"general-purpose"}}' | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$mutated" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
  echo 'deny-to-allow mutation unexpectedly passed' >&2
  exit 1
fi

echo 'hooks harness passed'
