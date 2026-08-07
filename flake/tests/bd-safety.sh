#!/usr/bin/env bash

set -euo pipefail

hook="$1"
test_root="$(mktemp -d)"
trap 'rm -rf "$test_root"' EXIT

run_hook() {
  local command="$1"
  printf '%s\n' "{\"tool_input\":{\"command\":$(printf '%s' "$command" | jq -Rs .)}}" | "$hook"
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

mutated="$test_root/mutated-hook"
cp "$hook" "$mutated"
sed -i 's/if \[\[ -n "\$bd_replace_reason" \]\]; then/if false; then/' "$mutated"
mutated_input="{\"tool_input\":{\"command\":$(printf '%s' 'bd update sinnix-test --notes note' | jq -Rs .)}}"
test -z "$(printf '%s\n' "$mutated_input" | "$mutated")"
