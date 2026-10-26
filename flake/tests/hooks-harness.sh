#!/usr/bin/env bash
# Provably fails when: a hook fails shellcheck, a guard stops denying what it
# should deny, or a hook blocks on malformed input.
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

bash_deny=$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"git push --force origin master"}}')
printf '%s' "$bash_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" '{"tool_input":{"command":"printf \"safe\""}}')"
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" 'not-json' 2>/dev/null)"

# Inspect every update in a compound command, including after a safe update.
for denied in 'bd update x --append-notes safe; bd update y --notes replace' 'bd update x --append-notes safe && bd update y --description replace'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.sh" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
payload=$(jq -cn --arg command 'bd update x --append-notes safe; bd update y --append-notes safe' '{tool_input: {command: $command}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$payload")"

# Leading shell whitespace must not bypass the lock guard. These commands
# are input to the hook only; the harness never invokes fastboot.
for denied in '  fastboot flashing lock' $'\tfastboot oem lock' '  sudo fastboot flashing lock_critical' 'true;  fastboot flashing lock'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.sh" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for allowed in '  fastboot flashing unlock' 'echo fastboot flashing lock'; do
  payload=$(jq -cn --arg command "$allowed" '{tool_input: {command: $command}}')
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$payload")"
done

# Hook bypass and checkout-wide stashes are denied; named-path stashes, stash
# inspection, and a heredoc message naming the flag stay allowed.
for denied in 'git commit --no-verify -m x' 'git commit -n -m x' 'git commit -anm x' 'git -c core.hooksPath=/dev/null commit -m x' 'git -C /tmp/r push --no-verify origin b' 'cd /tmp && git stash' 'git stash -u' 'git stash push -m wip' 'git stash save wip'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.sh" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for allowed in 'git commit -mn' 'git commit -m -n' 'git merge -n topic' 'git stash push -m wip -- a.txt' 'git stash list' 'git stash pop' 'git push origin b' $'git commit -F - <<\'EOF\'\nnever pass --no-verify\nEOF'; do
  payload=$(jq -cn --arg command "$allowed" '{tool_input: {command: $command}}')
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$payload")"
done

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
for command in \
  'until agentctl job result 559 | grep -q done; do sleep 30; done' \
  "timeout 590 bash -c 'until [ \"\$(gh pr view 2900 --json state -q .state)\" != OPEN ]; do sleep 30; done'" \
  'for i in $(seq 1 60); do gh pr checks 1 && break; sleep 10; done'; do
  payload=$(jq -n --arg command "$command" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.sh" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for payload in \
  "$(jq -n '{tool_input: {command: "until test -s out; do sleep 5; done", run_in_background: true}}')" \
  "$(jq -n '{tool_input: {command: "# poll-ok: socket appears within seconds\nuntil test -S sock; do sleep 1; done"}}')" \
  "$(jq -n '{tool_input: {command: "while read -r line; do echo \"$line\"; done < list"}}')" \
  "$(jq -n '{tool_input: {command: "git commit -F - <<EOF\nuntil x; do sleep 30; done\nEOF"}}')"; do
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.sh" "$payload")"
done

test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-sinex-recall.sh" '{}')"

cat >"$test_root/bin/sinexctl" <<'EOF'
#!/usr/bin/env bash
sleep 3
EOF
chmod +x "$test_root/bin/sinexctl"
PATH="$test_root/bin" SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS=1 \
  HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" \
  "$hooks_dir/sessionstart-sinex-recall.sh" </dev/null >/dev/null

echo 'hooks harness passed'
