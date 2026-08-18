#!/usr/bin/env bash
# Provably fails when: the hook stops denying a wrong-checkout git commit or a
# replace-write bd update from a worktree.

set -euo pipefail

hook="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

run_hook_at() {
  local cwd="$1"
  local command="$2"
  printf '%s\n' "{\"cwd\":$(printf '%s' "$cwd" | jq -Rs .),\"tool_input\":{\"command\":$(printf '%s' "$command" | jq -Rs .)}}" | "$hook"
}

run_hook() {
  local command="$1"
  run_hook_at "" "$command"
}

assert_denied() {
  local command="$1"
  run_hook "$command" | jq -e '.hookSpecificOutput.permissionDecision == "deny" and (.hookSpecificOutput.permissionDecisionReason | contains("bd update replace-writes blocked"))' >/dev/null
}

assert_allowed() {
  local command="$1"
  test -z "$(run_hook "$command")"
}

assert_denied 'bd update sinnix-test --notes "new note"'
assert_denied 'bd update sinnix-test --design "new design"'
assert_denied 'bd update sinnix-test -d "new description"'
assert_denied 'bd update sinnix-test --description="new description"'

assert_allowed 'bd update sinnix-test --append-notes "new note"'
assert_allowed 'bd update sinnix-test --design-file design.md --body-file body.md'
assert_allowed 'echo "bd update sinnix-test --notes quoted prose"'
assert_allowed 'printf -- "--notes"'
assert_allowed 'bd show sinnix-test --notes'
assert_allowed 'echo before; bd update sinnix-test --append-notes "new note"'

assert_checkout_denied() {
  local command="$1"
  run_hook_at /realm/worktrees/example "$command" | jq -e '.hookSpecificOutput.permissionDecision == "deny" and (.hookSpecificOutput.permissionDecisionReason | contains("wrong-checkout guard"))' >/dev/null
}

assert_checkout_allowed() {
  local command="$1"
  test -z "$(run_hook_at /realm/worktrees/example "$command")"
}

assert_checkout_denied 'git commit -m "checkpoint"'
assert_checkout_denied 'echo before; git commit -m "checkpoint"'
assert_checkout_denied 'bd export'
assert_checkout_denied 'bd export -o issues.jsonl'
assert_checkout_allowed 'git -C /realm/project/sinnix commit -m "checkpoint"'
assert_checkout_allowed 'bd -C /realm/project/sinnix export'
assert_checkout_allowed 'bd export -o /realm/tmp/issues.jsonl'
assert_checkout_allowed 'echo "git commit and bd export"'
assert_checkout_allowed 'git status'

mutated="$test_root/mutated-hook"
cp "$hook" "$mutated"
# Quoting inside [[ -n ... ]] is formatter-owned; match either form, and
# hard-fail if the mutation did not land -- a silently no-op mutation makes
# this whole test vacuous.
sed -i -E 's/if \[\[ -n "?\$bd_guard_reason"? \]\]; then/if false; then/' "$mutated"
grep -q 'if false; then' "$mutated"
mutated_input="{\"tool_input\":{\"command\":$(printf '%s' 'bd update sinnix-test --notes note' | jq -Rs .)}}"
test -z "$(printf '%s\n' "$mutated_input" | "$mutated")"
