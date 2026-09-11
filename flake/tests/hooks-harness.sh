#!/usr/bin/env bash
# Provably fails when: the Claude/Codex dispatch guard stops requiring explicit
# fresh-dispatch inputs, permits contradictory inheritance, interferes with a
# non-dispatch tool, fails shellcheck, or blocks on malformed input.
set -euo pipefail

hooks_dir=$1
settings=$2
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/home"
ln -s /run/current-system/sw/bin/jq "$test_root/bin/jq"
ln -s /run/current-system/sw/bin/timeout "$test_root/bin/timeout"
ln -s /run/current-system/sw/bin/bash "$test_root/bin/bash"
for tool in cat date dirname mkdir sleep; do
  ln -s "/run/current-system/sw/bin/$tool" "$test_root/bin/$tool"
done

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

model_deny=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","prompt":"fixture"}}')
printf '%s' "$model_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# Named Claude role types are no longer exempt: omitting model at the call site
# is a hard deny, while role/runner-owned effort remains unknown to this hook.
model_deny_named=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"review"}}')
printf '%s' "$model_deny_named" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# An explicit unoverridden Claude fork is deliberate inheritance, not a silent
# allow; requesting a model override is rejected because the hook cannot prove
# it was honored.
claude_fork=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"fork"}}')
printf '%s' "$claude_fork" | jq -e '.systemMessage | type == "string" and length > 0' >/dev/null
claude_fork_override=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"fork","model":"sonnet"}}')
printf '%s' "$claude_fork_override" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# A valid Claude role asks for a model, while the notification makes clear that
# requested fields are not the observed child identity.
model_confirm=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose","model":"sonnet"}}')
printf '%s' "$model_confirm" | jq -e '(.hookSpecificOutput.permissionDecision? != "deny") and (.systemMessage | type == "string" and length > 0)' >/dev/null
model_confirm_named=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"Agent","tool_input":{"subagent_type":"review","model":"opus"}}')
printf '%s' "$model_confirm_named" | jq -e '(.hookSpecificOutput.permissionDecision? != "deny") and (.systemMessage | type == "string" and length > 0)' >/dev/null

# Codex default fresh spawns must select model and supported effort with an
# explicit bounded context. Native roles and full forks may inherit their
# declared settings, which this hook cannot observe.
codex_missing=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"model":"gpt-5.6-terra","reasoning_effort":"high"}}')
printf '%s' "$codex_missing" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
codex_missing_model=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"none","reasoning_effort":"high"}}')
printf '%s' "$codex_missing_model" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
codex_missing_effort=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"2","model":"future-model"}}')
printf '%s' "$codex_missing_effort" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
codex_bad_effort=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"none","model":"future-model","reasoning_effort":"critical"}}')
printf '%s' "$codex_bad_effort" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
codex_full_named_role=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"all","agent_type":"reviewer"}}')
printf '%s' "$codex_full_named_role" | jq -e '(.hookSpecificOutput.permissionDecision? != "deny") and (.systemMessage | type == "string" and length > 0)' >/dev/null
codex_fresh_named_role=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"none","agent_type":"explorer"}}')
printf '%s' "$codex_fresh_named_role" | jq -e '(.hookSpecificOutput.permissionDecision? != "deny") and (.systemMessage | contains("cannot observe"))' >/dev/null
codex_inherit_model=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"none","model":"inherit","reasoning_effort":"high"}}')
printf '%s' "$codex_inherit_model" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
codex_fresh=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"none","model":"future-model","reasoning_effort":"ultra"}}')
printf '%s' "$codex_fresh" | jq -e '.systemMessage | type == "string" and length > 0' >/dev/null
codex_bounded=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"2","model":"future-model","reasoning_effort":"high"}}')
printf '%s' "$codex_bounded" | jq -e '.systemMessage | type == "string" and length > 0' >/dev/null
# An explicit full fork is the only inheritance path. Contradictory override
# intent is denied instead of pretending the selected model can be rewritten.
codex_inherit=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"all"}}')
printf '%s' "$codex_inherit" | jq -e '.systemMessage | type == "string" and length > 0' >/dev/null
codex_contradictory=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"spawn_agent","tool_input":{"fork_turns":"all","model":"gpt-5.6-terra"}}')
printf '%s' "$codex_contradictory" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
# The config matcher is exact, and the shared script leaves other lifecycle
# tools alone when invoked directly.
test -z "$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_name":"followup_task","tool_input":{"target":"worker"}}')"
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
if printf '%s' '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}' | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$mutated" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
  echo 'deny-to-allow mutation unexpectedly passed' >&2
  exit 1
fi

echo 'hooks harness passed'
