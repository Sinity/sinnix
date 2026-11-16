#!/usr/bin/env bash
# Provably fails when: a hook fails shellcheck, a guard stops denying what it
# should deny for either harness, a client's hook source stops running the
# command guard on shell commands, a hook blocks on malformed input, or the
# attention notification fires for a short turn or an unattended run, or stays
# silent when an attended session asks for the operator.
set -euo pipefail

hooks_dir=$1
settings=$2
codex_hooks=$3
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/home"
# A PATH holding only basic tools, taken from wherever this test runs (the
# build sandbox has no /run/current-system).
for tool in bash cat date dirname jq mkdir mktemp rm sleep timeout; do
  ln -s "$(command -v "$tool")" "$test_root/bin/$tool"
done

jq -e . "$settings" >/dev/null
shellcheck "$hooks_dir"/*.sh
for hook in "$hooks_dir"/*.sh; do
  bash -n "$hook"
done

# The hook is a command line, as in the harness settings: a path and arguments.
run_hook() {
  local payload=$2
  local -a hook
  read -r -a hook <<<"$1"
  export PATH
  printf '%s' "$payload" | HOME="$test_root/home" XDG_STATE_HOME="$test_root/state" "${hook[@]}"
}

bash_deny=$(run_hook "$hooks_dir/pretooluse-bash.py" '{"tool_input":{"command":"git push --force origin master"}}')
printf '%s' "$bash_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" '{"tool_input":{"command":"printf \"safe\""}}')"
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" 'not-json' 2>/dev/null)"

# Inspect every update in a compound command, including after a safe update.
for denied in 'bd update x --append-notes safe; bd update y --notes replace' 'bd update x --append-notes safe && bd update y --description replace'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.py" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
payload=$(jq -cn --arg command 'bd update x --append-notes safe; bd update y --append-notes safe' '{tool_input: {command: $command}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$payload")"

# Leading shell whitespace must not bypass the lock guard. These commands
# are input to the hook only; the harness never invokes fastboot.
for denied in '  fastboot flashing lock' $'\tfastboot oem lock' '  sudo fastboot flashing lock_critical' 'true;  fastboot flashing lock'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.py" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
# Shared job pools are not an agent's to pause, resume, resize or empty.
for denied in 'pueue pause --group bulk' 'pueue pause --wait --group compile' 'true; pueue start -g normal' 'pueue parallel 4 -g bulk' 'pueue clean' 'pueue kill --group bulk' 'agentctl pools apply'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.py" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for allowed in 'pueue status --json' 'pueue group' 'pueue kill 12' 'pueue log 12' 'echo pueue pause' 'SINNIX_POOL_CONTROL=1 pueue pause --group bulk' 'agentctl pools list'; do
  payload=$(jq -cn --arg command "$allowed" '{tool_input: {command: $command}}')
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$payload")"
done
for allowed in '  fastboot flashing unlock' 'echo fastboot flashing lock'; do
  payload=$(jq -cn --arg command "$allowed" '{tool_input: {command: $command}}')
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$payload")"
done

# Hook bypass and checkout-wide stashes are denied; named-path stashes, stash
# inspection, and a heredoc message naming the flag stay allowed.
for denied in 'git commit --no-verify -m x' 'git commit -n -m x' 'git commit -anm x' 'git -c core.hooksPath=/dev/null commit -m x' 'git -C /tmp/r push --no-verify origin b' 'git push -f origin b' 'rm -f /tmp/x; git push origin b --force' 'cd /tmp && git stash' 'git stash -u' 'git stash push -m wip' 'git stash save wip'; do
  payload=$(jq -cn --arg command "$denied" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.py" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for allowed in 'git commit -mn' 'git commit -m -n' 'git merge -n topic' 'git stash push -m wip -- a.txt' 'git stash list' 'git stash pop' 'git push origin b' 'git push origin b && rm -f /tmp/x' 'git push --force-with-lease origin b; rm -f /tmp/x' $'git commit -F - <<\'EOF\'\nnever pass --no-verify\nEOF'; do
  payload=$(jq -cn --arg command "$allowed" '{tool_input: {command: $command}}')
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$payload")"
done

# A shell glob over /nix/store makes the shell stat ~219k entries before the
# command runs; it has exhausted host memory twice. Deny the unquoted glob,
# keep concrete store paths and lazily-expanded quoted patterns working.
store_glob_payload=$(jq -n --arg c 'rg -n pattern /nix/store/*/share/doc/home-manager/*.html' '{tool_input:{command:$c}}')
store_glob_deny=$(run_hook "$hooks_dir/pretooluse-bash.py" "$store_glob_payload")
printf '%s' "$store_glob_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
store_path_payload=$(jq -n --arg c 'cat /nix/store/abc123-foo/bin/x' '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$store_path_payload")"
store_find_payload=$(jq -n --arg c "find /nix/store -maxdepth 1 -name '*home-manager*'" '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$store_find_payload")"
# A commit message or doc describing the hazard must be able to quote the
# pattern, so heredoc bodies are exempt -- but only until the heredoc closes.
store_heredoc_body=$(printf 'git commit -F - <<%sEOF%s\nfix: a pattern like /nix/store/*/share/doc/pkg/*.html stats the whole store\nEOF\n' "'" "'")
store_heredoc_payload=$(jq -n --arg c "$store_heredoc_body" '{tool_input:{command:$c}}')
test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$store_heredoc_payload")"
store_after_heredoc=$(printf 'cat <<%sEOF%s\ntext\nEOF\nls /nix/store/*\n' "'" "'")
store_after_payload=$(jq -n --arg c "$store_after_heredoc" '{tool_input:{command:$c}}')
store_after_deny=$(run_hook "$hooks_dir/pretooluse-bash.py" "$store_after_payload")
printf '%s' "$store_after_deny" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
for command in \
  'until agentctl job result 559 | grep -q done; do sleep 30; done' \
  "timeout 590 bash -c 'until [ \"\$(gh pr view 2900 --json state -q .state)\" != OPEN ]; do sleep 30; done'" \
  'for i in $(seq 1 60); do gh pr checks 1 && break; sleep 10; done'; do
  payload=$(jq -n --arg command "$command" '{tool_input: {command: $command}}')
  run_hook "$hooks_dir/pretooluse-bash.py" "$payload" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
done
for payload in \
  "$(jq -n '{tool_input: {command: "until test -s out; do sleep 5; done", run_in_background: true}}')" \
  "$(jq -n '{tool_input: {command: "# poll-ok: socket appears within seconds\nuntil test -S sock; do sleep 1; done"}}')" \
  "$(jq -n '{tool_input: {command: "while read -r line; do echo \"$line\"; done < list"}}')" \
  "$(jq -n '{tool_input: {command: "for j in 1 2; do agentctl job cancel $j; done; sleep 5; free -g"}}')" \
  "$(jq -n '{tool_input: {command: "git commit -F - <<EOF\nuntil x; do sleep 30; done\nEOF"}}')"; do
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.py" "$payload")"
done

# Codex sends the same payload shape for a shell command (`tool_name` Bash,
# the script in `tool_input.command`, the session directory in `cwd`) and reads
# the same deny answer. Its hook passes the harness name, which changes only
# the advice in a denial.
codex_payload() {
  jq -cn --arg command "$1" '{
    session_id: "s", turn_id: "t", tool_use_id: "u", hook_event_name: "PreToolUse",
    cwd: "/tmp/r", model: "m", permission_mode: "bypassPermissions",
    tool_name: "Bash", tool_input: {command: $command}
  }'
}
for denied in 'git stash' 'git push --force origin master' 'git commit --no-verify -m x' 'bd update x --notes replace' 'ls /nix/store/*' 'until test -s out; do sleep 30; done'; do
  run_hook "$hooks_dir/pretooluse-bash.py codex" "$(codex_payload "$denied")" |
    jq -e '.hookSpecificOutput.hookEventName == "PreToolUse" and .hookSpecificOutput.permissionDecision == "deny" and (.hookSpecificOutput.permissionDecisionReason | length > 0)' >/dev/null
done
for allowed in 'git status --short' 'git stash push -m wip -- a.txt' 'git push origin b' $'# poll-ok: socket appears within seconds\nuntil test -S sock; do sleep 1; done'; do
  test -z "$(run_hook "$hooks_dir/pretooluse-bash.py codex" "$(codex_payload "$allowed")")"
done
# Each harness is pointed at tools it has: only Claude Code can background a call.
poll_payload=$(codex_payload 'until test -s out; do sleep 30; done')
run_hook "$hooks_dir/pretooluse-bash.py" "$poll_payload" |
  jq -e '.hookSpecificOutput.permissionDecisionReason | contains("run_in_background")' >/dev/null
run_hook "$hooks_dir/pretooluse-bash.py codex" "$poll_payload" |
  jq -e '.hookSpecificOutput.permissionDecisionReason | contains("run_in_background") | not' >/dev/null

# Both clients run the guard on their shell tool, and Codex names itself.
jq -e '
  [.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[].command]
  | any(endswith("/pretooluse-bash.py"))
' "$settings" >/dev/null
jq -e '
  [.hooks.PreToolUse[] | select(.matcher == "^Bash$") | .hooks[].command]
  | any(endswith("/pretooluse-bash.py codex"))
' "$codex_hooks" >/dev/null

# The attention hook notifies only from an attended harness: an ancestor named
# after the harness with a terminal on stdin and stdout, started interactively.
# A stand-in executable of that name, run under a pseudo-terminal, is one.
mkdir -p "$test_root/harness" "$test_root/stub" "$test_root/run"
for name in claude codex; do
  cat >"$test_root/harness/$name" <<EOF
#!$test_root/bin/bash
read -r -a hook <<<"\$ATTENTION_HOOK"
printf '%s' "\$ATTENTION_PAYLOAD" | "\${hook[@]}"
EOF
  chmod +x "$test_root/harness/$name"
done
cat >"$test_root/stub/notify-send" <<EOF
#!$test_root/bin/bash
printf '%s\n' "\$@" >"$test_root/notice"
EOF
chmod +x "$test_root/stub/notify-send"
attention_env() {
  env PATH="$test_root/stub:$PATH" XDG_RUNTIME_DIR="$test_root/run" HYPRLAND_INSTANCE_SIGNATURE= \
    ATTENTION_HOOK="$1" ATTENTION_PAYLOAD="$2" "${@:3}"
}
# attended <harness> <hook arguments> <payload> [harness arguments]
attended() {
  attention_env "$hooks_dir/attention-notify.py $2" "$3" \
    script -qec "$test_root/harness/$1 ${4:-}" /dev/null >/dev/null </dev/null
}
# The sender is started detached, so its record can trail the hook's exit.
expect_notice() {
  local waited=0
  while ! test -s "$test_root/notice" && ((waited < 60)); do
    sleep 0.05
    waited=$((waited + 1))
  done
  grep -qxF -- "$1" "$test_root/notice"
  grep -qxF -- "$2" "$test_root/notice"
  grep -qxF -- '--app-name=agent-attention' "$test_root/notice"
  rm "$test_root/notice"
}
expect_silence() {
  sleep 0.3
  test ! -e "$test_root/notice"
}
attention_payload() {
  jq -cn --arg event "$1" --arg type "${2:-}" '{
    session_id: "s1", cwd: "/work/example-project", hook_event_name: $event,
    notification_type: $type, tool_name: "Bash"
  }'
}
stamp="$test_root/run/sinnix-agent-turn/claude-s1"

attended claude '' "$(attention_payload Notification permission_prompt)"
expect_notice 'example-project (Claude Code)' 'needs permission'
attended claude '' "$(attention_payload Notification elicitation_dialog)"
expect_notice 'example-project (Claude Code)' 'asks a question'
attended codex codex "$(attention_payload PermissionRequest)"
expect_notice 'example-project (Codex)' 'needs permission for Bash'
# A checkout kept as <project>/repo is named by its project folder.
attended claude '' "$(attention_payload Notification permission_prompt | jq -c '.cwd = "/work/example-project/repo"')"
expect_notice 'example-project (Claude Code)' 'needs permission'
# Waiting at the prompt after a turn is not a request.
attended claude '' "$(attention_payload Notification idle_prompt)"
expect_silence

# A short turn is silent; one longer than ten minutes is announced once.
attended claude '' "$(attention_payload UserPromptSubmit)"
test -e "$stamp"
attended claude '' "$(attention_payload Stop)"
expect_silence
test ! -e "$stamp"
attended claude '' "$(attention_payload UserPromptSubmit)"
touch -d '11 minutes ago' "$stamp"
attended claude '' "$(attention_payload Stop)"
expect_notice 'example-project (Claude Code)' 'finished after 11 min'
attended claude '' "$(attention_payload Stop)"
expect_silence

# Unattended: no terminal, or a non-interactive start. Nothing is stamped.
attention_env "$hooks_dir/attention-notify.py" "$(attention_payload Notification permission_prompt)" \
  "$test_root/harness/claude" >/dev/null </dev/null
expect_silence
attended claude '' "$(attention_payload Notification permission_prompt)" '-p prompt'
expect_silence
attended codex codex "$(attention_payload PermissionRequest)" 'exec prompt'
expect_silence
attended claude '' "$(attention_payload UserPromptSubmit)" '--print prompt'
test ! -e "$stamp"
# The harness the hook names must be its ancestor: a Codex hook under a
# process named claude finds no Codex.
attended claude codex "$(attention_payload PermissionRequest)"
expect_silence
# Malformed input is a silent success.
test -z "$(attention_env "$hooks_dir/attention-notify.py" 'not-json' "$test_root/harness/claude" 2>&1)"

# Both clients run it on the events that carry the two cases.
jq -e --arg hook attention-notify.py '
  def runs($event): [.hooks[$event][]?.hooks[].command] | any(endswith("/" + $hook));
  runs("UserPromptSubmit") and runs("Stop") and runs("Notification")
  and ([.hooks.Notification[] | select(.hooks[].command | endswith("/" + $hook)) | .matcher]
       == ["permission_prompt|elicitation_dialog"])
  and ([.hooks.PreToolUse[] | select(.matcher == "AskUserQuestion") | .hooks[].command]
       | any(endswith("/" + $hook)))
' "$settings" >/dev/null
jq -e --arg hook 'attention-notify.py codex' '
  def runs($event): [.hooks[$event][]?.hooks[].command] | any(endswith("/" + $hook));
  runs("UserPromptSubmit") and runs("Stop") and runs("PermissionRequest")
' "$codex_hooks" >/dev/null

# Without Polylogue, Sinnix or Sinex on PATH the session-start block is empty.
test -z "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-context.sh" '{"source":"startup"}')"

# A hung Sinex status is cut off by its timeout and drops only its part.
cat >"$test_root/bin/sinexctl" <<EOF
#!$test_root/bin/bash
sleep 3
EOF
chmod +x "$test_root/bin/sinexctl"
test -z "$(PATH="$test_root/bin" SINEX_SESSIONSTART_RECALL_TIMEOUT_SECS=1 \
  run_hook "$hooks_dir/sessionstart-context.sh" '{"source":"startup"}')"

# One block, the brief first: a stub Polylogue brief and a stub Sinex source.
cat >"$test_root/bin/polylogue" <<EOF
#!$test_root/bin/bash
cat >/dev/null
printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"BRIEF"}}'
EOF
cat >"$test_root/bin/sinexctl" <<EOF
#!$test_root/bin/bash
printf '{"sources":[{"binding":"fixture","last_event":"%s"}]}\n' "\$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF
chmod +x "$test_root/bin/polylogue" "$test_root/bin/sinexctl"
block=$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-context.sh" '{"source":"startup"}' |
  jq -r '.hookSpecificOutput.additionalContext')
case $block in
  BRIEF$'\n\n'"Sinex sources"*fixture*) ;;
  *)
    echo "session-start block has the wrong order or parts: $block" >&2
    exit 1
    ;;
esac
# After compaction only the brief comes back.
test "$(PATH="$test_root/bin" run_hook "$hooks_dir/sessionstart-context.sh" '{"source":"compact"}' |
  jq -r '.hookSpecificOutput.additionalContext')" = BRIEF

echo 'hooks harness passed'
