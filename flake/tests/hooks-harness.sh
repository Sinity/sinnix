#!/usr/bin/env bash
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
  printf '%s' "$payload" | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "$hook"
}

model_deny=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"general-purpose","prompt":"fixture"}}')
printf '%s' "$model_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
model_warn=$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"review"}}')
printf '%s' "$model_warn" | jq -e '.systemMessage | contains("omits model")' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-agent-model.sh" '{"tool_input":{"subagent_type":"general-purpose","model":"sonnet"}}')"
test -z "$(run_hook "$hooks_dir/pretooluse-agent-model.sh" 'not-json')"

bash_deny=$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"git push --force origin master"}}')
printf '%s' "$bash_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"printf \"safe\""}}')"
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" 'not-json' 2>/dev/null)"

test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/subagentstop-dispatch-ledger.sh" '{}')"
test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-beads-prime.sh" '{}')"
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
